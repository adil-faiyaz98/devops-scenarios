package rollout

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"math/rand"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/service/dynamodb"
	"github.com/aws/aws-sdk-go-v2/service/dynamodb/types"
	"github.com/aws/aws-sdk-go-v2/service/s3"
	"github.com/google/uuid"
)

// RolloutPhase represents a phase in the progressive rollout
type RolloutPhase struct {
	ID              string    `json:"id"`
	Percentage      float64   `json:"percentage"`
	StartTime       time.Time `json:"startTime"`
	Duration        string    `json:"duration"`
	RequireApproval bool      `json:"requireApproval"`
	Approved        bool      `json:"approved"`
	Metrics         []string  `json:"metrics"`
	Thresholds      map[string]float64 `json:"thresholds"`
}

// RolloutPlan represents a complete progressive rollout plan
type RolloutPlan struct {
	ID             string         `json:"id"`
	Name           string         `json:"name"`
	Description    string         `json:"description"`
	Version        string         `json:"version"`
	CreatedAt      time.Time      `json:"createdAt"`
	UpdatedAt      time.Time      `json:"updatedAt"`
	Status         string         `json:"status"` // pending, in-progress, completed, failed, rolled-back
	Phases         []RolloutPhase `json:"phases"`
	CurrentPhase   int            `json:"currentPhase"`
	PackageURL     string         `json:"packageUrl"`
	PackageHash    string         `json:"packageHash"`
	TargetGroups   []string       `json:"targetGroups"`
	RollbackPlan   string         `json:"rollbackPlan"`
	CreatedBy      string         `json:"createdBy"`
}

// RolloutManager handles progressive rollouts to edge devices
type RolloutManager struct {
	dynamoClient       *dynamodb.Client
	s3Client           *s3.Client
	deviceID           string
	deviceGroup        string
	deviceTags         map[string]string
	rolloutTableName   string
	deviceTableName    string
	updateBasePath     string
	currentRollout     *RolloutPlan
	rolloutMutex       sync.RWMutex
	updateHandlers     []UpdateHandler
	telemetryReporters []TelemetryReporter
	healthChecks       []HealthCheck
	lastCheckTime      time.Time
	checkInterval      time.Duration
	checkTimer         *time.Timer
}

// UpdateHandler is an interface for handling updates
type UpdateHandler interface {
	// HandleUpdate processes an update package
	HandleUpdate(packagePath string, version string) error
	
	// ValidateUpdate validates an update package before applying
	ValidateUpdate(packagePath string) error
	
	// RollbackUpdate rolls back to the previous version
	RollbackUpdate() error
}

// TelemetryReporter is an interface for reporting telemetry data
type TelemetryReporter interface {
	// ReportMetrics reports metrics for rollout monitoring
	ReportMetrics(metrics []string) error
}

// HealthCheck is an interface for checking the health of the system
type HealthCheck interface {
	// CheckHealth performs a health check
	CheckHealth() (bool, error)
}

// RolloutConfig contains configuration for the RolloutManager
type RolloutConfig struct {
	DynamoClient     *dynamodb.Client
	S3Client         *s3.Client
	DeviceID         string
	DeviceGroup      string
	DeviceTags       map[string]string
	RolloutTableName string
	DeviceTableName  string
	UpdateBasePath   string
	CheckInterval    time.Duration
}

// NewRolloutManager creates a new RolloutManager
func NewRolloutManager(config RolloutConfig) (*RolloutManager, error) {
	// Create update directory if it doesn't exist
	if err := os.MkdirAll(config.UpdateBasePath, 0755); err != nil {
		return nil, fmt.Errorf("failed to create update directory: %w", err)
	}

	rm := &RolloutManager{
		dynamoClient:       config.DynamoClient,
		s3Client:           config.S3Client,
		deviceID:           config.DeviceID,
		deviceGroup:        config.DeviceGroup,
		deviceTags:         config.DeviceTags,
		rolloutTableName:   config.RolloutTableName,
		deviceTableName:    config.DeviceTableName,
		updateBasePath:     config.UpdateBasePath,
		updateHandlers:     make([]UpdateHandler, 0),
		telemetryReporters: make([]TelemetryReporter, 0),
		healthChecks:       make([]HealthCheck, 0),
		checkInterval:      config.CheckInterval,
	}

	// Start the check timer
	rm.checkTimer = time.AfterFunc(rm.checkInterval, rm.checkForUpdates)

	return rm, nil
}

// RegisterUpdateHandler registers a handler for updates
func (rm *RolloutManager) RegisterUpdateHandler(handler UpdateHandler) {
	rm.updateHandlers = append(rm.updateHandlers, handler)
}

// RegisterTelemetryReporter registers a reporter for telemetry data
func (rm *RolloutManager) RegisterTelemetryReporter(reporter TelemetryReporter) {
	rm.telemetryReporters = append(rm.telemetryReporters, reporter)
}

// RegisterHealthCheck registers a health check
func (rm *RolloutManager) RegisterHealthCheck(check HealthCheck) {
	rm.healthChecks = append(rm.healthChecks, check)
}

// checkForUpdates checks for available updates
func (rm *RolloutManager) checkForUpdates() {
	defer func() {
		// Reschedule the check
		rm.checkTimer.Reset(rm.checkInterval)
	}()

	// Get device information
	deviceInfo, err := rm.getDeviceInfo()
	if err != nil {
		log.Printf("Failed to get device info: %v", err)
		return
	}

	// Check if there's an active rollout for this device
	rollout, err := rm.getActiveRollout(deviceInfo)
	if err != nil {
		log.Printf("Failed to get active rollout: %v", err)
		return
	}

	if rollout == nil {
		// No active rollout
		return
	}

	// Update current rollout
	rm.rolloutMutex.Lock()
	rm.currentRollout = rollout
	rm.rolloutMutex.Unlock()

	// Check if we should apply this update
	if rm.shouldApplyUpdate(rollout) {
		if err := rm.applyUpdate(rollout); err != nil {
			log.Printf("Failed to apply update: %v", err)
			
			// Report failure
			if err := rm.reportUpdateStatus(rollout.ID, "failed", err.Error()); err != nil {
				log.Printf("Failed to report update failure: %v", err)
			}
			
			// Attempt rollback
			if err := rm.rollbackUpdate(); err != nil {
				log.Printf("Failed to rollback update: %v", err)
			}
		} else {
			// Report success
			if err := rm.reportUpdateStatus(rollout.ID, "success", ""); err != nil {
				log.Printf("Failed to report update success: %v", err)
			}
		}
	}
}

// getDeviceInfo retrieves information about this device
func (rm *RolloutManager) getDeviceInfo() (map[string]interface{}, error) {
	result, err := rm.dynamoClient.GetItem(context.Background(), &dynamodb.GetItemInput{
		TableName: aws.String(rm.deviceTableName),
		Key: map[string]types.AttributeValue{
			"DeviceID": &types.AttributeValueMemberS{Value: rm.deviceID},
		},
	})
	
	if err != nil {
		return nil, fmt.Errorf("failed to get device info: %w", err)
	}
	
	if result.Item == nil {
		return nil, fmt.Errorf("device not found: %s", rm.deviceID)
	}
	
	// Convert DynamoDB item to map
	deviceInfo := make(map[string]interface{})
	
	for k, v := range result.Item {
		switch av := v.(type) {
		case *types.AttributeValueMemberS:
			deviceInfo[k] = av.Value
		case *types.AttributeValueMemberN:
			deviceInfo[k] = av.Value
		case *types.AttributeValueMemberBOOL:
			deviceInfo[k] = av.Value
		case *types.AttributeValueMemberM:
			// Handle map attributes
			mapAttr := make(map[string]interface{})
			for mk, mv := range av.Value {
				if mvs, ok := mv.(*types.AttributeValueMemberS); ok {
					mapAttr[mk] = mvs.Value
				}
			}
			deviceInfo[k] = mapAttr
		case *types.AttributeValueMemberL:
			// Handle list attributes
			listAttr := make([]interface{}, 0, len(av.Value))
			for _, lv := range av.Value {
				if lvs, ok := lv.(*types.AttributeValueMemberS); ok {
					listAttr = append(listAttr, lvs.Value)
				}
			}
			deviceInfo[k] = listAttr
		}
	}
	
	return deviceInfo, nil
}

// getActiveRollout gets the active rollout for this device
func (rm *RolloutManager) getActiveRollout(deviceInfo map[string]interface{}) (*RolloutPlan, error) {
	// Query for active rollouts that target this device's group
	result, err := rm.dynamoClient.Query(context.Background(), &dynamodb.QueryInput{
		TableName:              aws.String(rm.rolloutTableName),
		IndexName:              aws.String("StatusIndex"),
		KeyConditionExpression: aws.String("Status = :status"),
		ExpressionAttributeValues: map[string]types.AttributeValue{
			":status": &types.AttributeValueMemberS{Value: "in-progress"},
		},
	})
	
	if err != nil {
		return nil, fmt.Errorf("failed to query active rollouts: %w", err)
	}
	
	if len(result.Items) == 0 {
		return nil, nil
	}
	
	// Find a rollout that targets this device
	for _, item := range result.Items {
		var rollout RolloutPlan
		
		// Extract rollout ID
		if id, ok := item["ID"].(*types.AttributeValueMemberS); ok {
			rollout.ID = id.Value
		} else {
			continue
		}
		
		// Extract target groups
		if targetGroups, ok := item["TargetGroups"].(*types.AttributeValueMemberL); ok {
			for _, tg := range targetGroups.Value {
				if tgs, ok := tg.(*types.AttributeValueMemberS); ok {
					rollout.TargetGroups = append(rollout.TargetGroups, tgs.Value)
				}
			}
		}
		
		// Check if this device is in the target group
		isTargeted := false
		for _, group := range rollout.TargetGroups {
			if group == rm.deviceGroup || group == "all" {
				isTargeted = true
				break
			}
		}
		
		if !isTargeted {
			continue
		}
		
		// Extract other rollout details
		if name, ok := item["Name"].(*types.AttributeValueMemberS); ok {
			rollout.Name = name.Value
		}
		
		if desc, ok := item["Description"].(*types.AttributeValueMemberS); ok {
			rollout.Description = desc.Value
		}
		
		if version, ok := item["Version"].(*types.AttributeValueMemberS); ok {
			rollout.Version = version.Value
		}
		
		if status, ok := item["Status"].(*types.AttributeValueMemberS); ok {
			rollout.Status = status.Value
		}
		
		if packageURL, ok := item["PackageURL"].(*types.AttributeValueMemberS); ok {
			rollout.PackageURL = packageURL.Value
		}
		
		if packageHash, ok := item["PackageHash"].(*types.AttributeValueMemberS); ok {
			rollout.PackageHash = packageHash.Value
		}
		
		if currentPhase, ok := item["CurrentPhase"].(*types.AttributeValueMemberN); ok {
			phase, _ := parseInt(currentPhase.Value)
			rollout.CurrentPhase = phase
		}
		
		// Extract phases
		if phasesAttr, ok := item["Phases"].(*types.AttributeValueMemberL); ok {
			for _, phaseAttr := range phasesAttr.Value {
				if phaseMap, ok := phaseAttr.(*types.AttributeValueMemberM); ok {
					var phase RolloutPhase
					
					if id, ok := phaseMap.Value["ID"].(*types.AttributeValueMemberS); ok {
						phase.ID = id.Value
					}
					
					if pct, ok := phaseMap.Value["Percentage"].(*types.AttributeValueMemberN); ok {
						phase.Percentage, _ = parseFloat(pct.Value)
					}
					
					if startTime, ok := phaseMap.Value["StartTime"].(*types.AttributeValueMemberS); ok {
						phase.StartTime, _ = time.Parse(time.RFC3339, startTime.Value)
					}
					
					if duration, ok := phaseMap.Value["Duration"].(*types.AttributeValueMemberS); ok {
						phase.Duration = duration.Value
					}
					
					if reqApproval, ok := phaseMap.Value["RequireApproval"].(*types.AttributeValueMemberBOOL); ok {
						phase.RequireApproval = reqApproval.Value
					}
					
					if approved, ok := phaseMap.Value["Approved"].(*types.AttributeValueMemberBOOL); ok {
						phase.Approved = approved.Value
					}
					
					rollout.Phases = append(rollout.Phases, phase)
				}
			}
		}
		
		return &rollout, nil
	}
	
	return nil, nil
}

// shouldApplyUpdate determines if this device should apply the update
func (rm *RolloutManager) shouldApplyUpdate(rollout *RolloutPlan) bool {
	// Check if we're already on this version
	currentVersion, err := rm.getCurrentVersion()
	if err != nil {
		log.Printf("Failed to get current version: %v", err)
		return false
	}
	
	if currentVersion == rollout.Version {
		return false
	}
	
	// Check if we're in the current phase's percentage
	if rollout.CurrentPhase >= len(rollout.Phases) {
		return false
	}
	
	currentPhase := rollout.Phases[rollout.CurrentPhase]
	
	// Check if the phase requires approval and hasn't been approved
	if currentPhase.RequireApproval && !currentPhase.Approved {
		return false
	}
	
	// Use device ID to deterministically decide if we're in the percentage
	// This ensures the same devices get updated in each phase
	h := fnv.New32a()
	h.Write([]byte(rm.deviceID))
	hash := h.Sum32()
	
	// Convert hash to a percentage (0-100)
	devicePercentile := float64(hash % 100)
	
	return devicePercentile <= currentPhase.Percentage
}

// applyUpdate applies an update
func (rm *RolloutManager) applyUpdate(rollout *RolloutPlan) error {
	// Download the update package
	packagePath, err := rm.downloadUpdatePackage(rollout.PackageURL, rollout.PackageHash)
	if err != nil {
		return fmt.Errorf("failed to download update package: %w", err)
	}
	
	// Validate the update with all handlers
	for _, handler := range rm.updateHandlers {
		if err := handler.ValidateUpdate(packagePath); err != nil {
			return fmt.Errorf("update validation failed: %w", err)
		}
	}
	
	// Apply the update with all handlers
	for _, handler := range rm.updateHandlers {
		if err := handler.HandleUpdate(packagePath, rollout.Version); err != nil {
			return fmt.Errorf("update application failed: %w", err)
		}
	}
	
	// Perform health checks
	healthy, err := rm.performHealthChecks()
	if err != nil || !healthy {
		return fmt.Errorf("health check failed after update: %w", err)
	}
	
	return nil
}

// downloadUpdatePackage downloads an update package
func (rm *RolloutManager) downloadUpdatePackage(packageURL, expectedHash string) (string, error) {
	// Extract the package name from the URL
	packageName := filepath.Base(packageURL)
	packagePath := filepath.Join(rm.updateBasePath, packageName)
	
	// Parse the S3 URL
	// Assuming format: s3://bucket-name/path/to/package
	s3URL := packageURL[5:] // Remove "s3://"
	parts := strings.SplitN(s3URL, "/", 2)
	if len(parts) != 2 {
		return "", fmt.Errorf("invalid S3 URL format: %s", packageURL)
	}
	
	bucketName := parts[0]
	objectKey := parts[1]
	
	// Download the package
	result, err := rm.s3Client.GetObject(context.Background(), &s3.GetObjectInput{
		Bucket: aws.String(bucketName),
		Key:    aws.String(objectKey),
	})
	
	if err != nil {
		return "", fmt.Errorf("failed to download package: %w", err)
	}
	
	// Create the file
	file, err := os.Create(packagePath)
	if err != nil {
		return "", fmt.Errorf("failed to create package file: %w", err)
	}
	defer file.Close()
	
	// Copy the data
	_, err = io.Copy(file, result.Body)
	if err != nil {
		return "", fmt.Errorf("failed to write package file: %w", err)
	}
	
	// Verify the hash
	hash, err := calculateFileHash(packagePath)
	if err != nil {
		return "", fmt.Errorf("failed to calculate package hash: %w", err)
	}
	
	if hash != expectedHash {
		os.Remove(packagePath)
		return "", fmt.Errorf("package hash mismatch: expected %s, got %s", expectedHash, hash)
	}
	
	return packagePath, nil
}

// performHealthChecks runs all registered health checks
func (rm *RolloutManager) performHealthChecks() (bool, error) {
	for _, check := range rm.healthChecks {
		healthy, err := check.CheckHealth()
		if err != nil {
			return false, fmt.Errorf("health check error: %w", err)
		}
		
		if !healthy {
			return false, nil
		}
	}
	
	return true, nil
}

// rollbackUpdate rolls back to the previous version
func (rm *RolloutManager) rollbackUpdate() error {
	for _, handler := range rm.updateHandlers {
		if err := handler.RollbackUpdate(); err != nil {
			return fmt.Errorf("rollback failed: %w", err)
		}
	}
	
	return nil
}

// reportUpdateStatus reports the status of an update
func (rm *RolloutManager) reportUpdateStatus(rolloutID, status, message string) error {
	_, err := rm.dynamoClient.UpdateItem(context.Background(), &dynamodb.UpdateItemInput{
		TableName: aws.String(rm.deviceTableName),
		Key: map[string]types.AttributeValue{
			"DeviceID": &types.AttributeValueMemberS{Value: rm.deviceID},
		},
		UpdateExpression: aws.String("SET UpdateStatus = :status, LastUpdateID = :rolloutID, LastUpdateTime = :time, LastUpdateMessage = :message"),
		ExpressionAttributeValues: map[string]types.AttributeValue{
			":status":   &types.AttributeValueMemberS{Value: status},
			":rolloutID": &types.AttributeValueMemberS{Value: rolloutID},
			":time":     &types.AttributeValueMemberS{Value: time.Now().UTC().Format(time.RFC3339)},
			":message":  &types.AttributeValueMemberS{Value: message},
		},
	})
	
	return err
}

// getCurrentVersion gets the current version of the device
func (rm *RolloutManager) getCurrentVersion() (string, error) {
	result, err := rm.dynamoClient.GetItem(context.Background(), &dynamodb.GetItemInput{
		TableName: aws.String(rm.deviceTableName),
		Key: map[string]types.AttributeValue{
			"DeviceID": &types.AttributeValueMemberS{Value: rm.deviceID},
		},
		ProjectionExpression: aws.String("CurrentVersion"),
	})
	
	if err != nil {
		return "", fmt.Errorf("failed to get current version: %w", err)
	}
	
	if result.Item == nil {
		return "", fmt.Errorf("device not found: %s", rm.deviceID)
	}
	
	if version, ok := result.Item["CurrentVersion"].(*types.AttributeValueMemberS); ok {
		return version.Value, nil
	}
	
	return "", fmt.Errorf("current version not found")
}

// Close stops the rollout manager
func (rm *RolloutManager) Close() {
	if rm.checkTimer != nil {
		rm.checkTimer.Stop()
	}
}

// Helper functions

func parseInt(s string) (int, error) {
	i, err := strconv.Atoi(s)
	if err != nil {
		return 0, err
	}
	return i, nil
}

func parseFloat(s string) (float64, error) {
	f, err := strconv.ParseFloat(s, 64)
	if err != nil {
		return 0, err
	}
	return f, nil
}

func calculateFileHash(filePath string) (string, error) {
	file, err := os.Open(filePath)
	if err != nil {
		return "", err
	}
	defer file.Close()
	
	hash := sha256.New()
	if _, err := io.Copy(hash, file); err != nil {
		return "", err
	}
	
	return fmt.Sprintf("%x", hash.Sum(nil)), nil
}
