package offlineSync

import (
	"context"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/service/s3"
	"github.com/dgraph-io/badger/v3"
	"github.com/robfig/cron/v3"
)

// SyncManager handles offline operations and synchronized updates for edge devices
type SyncManager struct {
	db              *badger.DB
	s3Client        *s3.Client
	syncBucket      string
	deviceID        string
	localCachePath  string
	syncInterval    time.Duration
	syncCron        *cron.Cron
	lastSyncTime    time.Time
	pendingChanges  map[string][]byte
	changesMutex    sync.Mutex
	isOnline        bool
	onlineStatusMux sync.Mutex
	syncInProgress  bool
	syncMux         sync.Mutex
	syncHandlers    map[string]SyncHandler
}

// SyncHandler is an interface for handling different types of synchronized data
type SyncHandler interface {
	ProcessUpdate(key string, data []byte) error
	GetLocalChanges() (map[string][]byte, error)
	MergeConflicts(localData, remoteData []byte) ([]byte, error)
}

// SyncConfig contains configuration for the SyncManager
type SyncConfig struct {
	DeviceID        string
	LocalCachePath  string
	SyncBucket      string
	SyncInterval    time.Duration
	BadgerDBPath    string
	S3Client        *s3.Client
}

// NewSyncManager creates a new SyncManager
func NewSyncManager(config SyncConfig) (*SyncManager, error) {
	// Create local cache directory if it doesn't exist
	if err := os.MkdirAll(config.LocalCachePath, 0755); err != nil {
		return nil, fmt.Errorf("failed to create local cache directory: %w", err)
	}

	// Open BadgerDB for local storage
	opts := badger.DefaultOptions(config.BadgerDBPath)
	opts.Logger = nil // Disable logging
	db, err := badger.Open(opts)
	if err != nil {
		return nil, fmt.Errorf("failed to open BadgerDB: %w", err)
	}

	sm := &SyncManager{
		db:              db,
		s3Client:        config.S3Client,
		syncBucket:      config.SyncBucket,
		deviceID:        config.DeviceID,
		localCachePath:  config.LocalCachePath,
		syncInterval:    config.SyncInterval,
		pendingChanges:  make(map[string][]byte),
		isOnline:        false,
		syncHandlers:    make(map[string]SyncHandler),
		syncCron:        cron.New(),
	}

	// Schedule periodic sync
	_, err = sm.syncCron.AddFunc(fmt.Sprintf("@every %s", config.SyncInterval.String()), func() {
		if err := sm.Sync(); err != nil {
			log.Printf("Scheduled sync failed: %v", err)
		}
	})
	if err != nil {
		return nil, fmt.Errorf("failed to schedule sync: %w", err)
	}

	sm.syncCron.Start()
	return sm, nil
}

// RegisterSyncHandler registers a handler for a specific data type
func (sm *SyncManager) RegisterSyncHandler(dataType string, handler SyncHandler) {
	sm.syncHandlers[dataType] = handler
}

// SetOnlineStatus updates the online status of the device
func (sm *SyncManager) SetOnlineStatus(online bool) {
	sm.onlineStatusMux.Lock()
	defer sm.onlineStatusMux.Unlock()
	
	wasOnline := sm.isOnline
	sm.isOnline = online
	
	// If we just came online, trigger a sync
	if !wasOnline && online {
		go func() {
			if err := sm.Sync(); err != nil {
				log.Printf("Auto-sync on reconnection failed: %v", err)
			}
		}()
	}
}

// IsOnline returns the current online status
func (sm *SyncManager) IsOnline() bool {
	sm.onlineStatusMux.Lock()
	defer sm.onlineStatusMux.Unlock()
	return sm.isOnline
}

// AddPendingChange adds a change to be synchronized when online
func (sm *SyncManager) AddPendingChange(key string, data []byte) error {
	sm.changesMutex.Lock()
	defer sm.changesMutex.Unlock()
	
	// Store in memory
	sm.pendingChanges[key] = data
	
	// Store in BadgerDB for persistence
	err := sm.db.Update(func(txn *badger.Txn) error {
		return txn.Set([]byte(key), data)
	})
	if err != nil {
		return fmt.Errorf("failed to store pending change: %w", err)
	}
	
	// If we're online, try to sync immediately
	if sm.IsOnline() {
		go func() {
			if err := sm.Sync(); err != nil {
				log.Printf("Auto-sync after change failed: %v", err)
			}
		}()
	}
	
	return nil
}

// GetLocalData retrieves data from local cache
func (sm *SyncManager) GetLocalData(key string) ([]byte, error) {
	// First check in-memory cache
	sm.changesMutex.Lock()
	if data, ok := sm.pendingChanges[key]; ok {
		sm.changesMutex.Unlock()
		return data, nil
	}
	sm.changesMutex.Unlock()
	
	// Then check BadgerDB
	var result []byte
	err := sm.db.View(func(txn *badger.Txn) error {
		item, err := txn.Get([]byte(key))
		if err != nil {
			return err
		}
		
		return item.Value(func(val []byte) error {
			result = append([]byte{}, val...)
			return nil
		})
	})
	
	if err == badger.ErrKeyNotFound {
		// Finally check file system cache
		filePath := filepath.Join(sm.localCachePath, key)
		if _, err := os.Stat(filePath); err == nil {
			return ioutil.ReadFile(filePath)
		}
		return nil, fmt.Errorf("data not found for key: %s", key)
	}
	
	return result, err
}

// Sync synchronizes data with the cloud
func (sm *SyncManager) Sync() error {
	// Prevent multiple syncs from running concurrently
	sm.syncMux.Lock()
	if sm.syncInProgress {
		sm.syncMux.Unlock()
		return nil
	}
	sm.syncInProgress = true
	sm.syncMux.Unlock()
	
	defer func() {
		sm.syncMux.Lock()
		sm.syncInProgress = false
		sm.syncMux.Unlock()
	}()
	
	// Skip if offline
	if !sm.IsOnline() {
		return nil
	}
	
	// 1. Upload pending changes
	if err := sm.uploadPendingChanges(); err != nil {
		return fmt.Errorf("failed to upload pending changes: %w", err)
	}
	
	// 2. Download updates
	if err := sm.downloadUpdates(); err != nil {
		return fmt.Errorf("failed to download updates: %w", err)
	}
	
	// Update last sync time
	sm.lastSyncTime = time.Now()
	
	return nil
}

// uploadPendingChanges uploads all pending changes to S3
func (sm *SyncManager) uploadPendingChanges() error {
	// Collect all pending changes from handlers
	allChanges := make(map[string][]byte)
	
	// Add changes from memory
	sm.changesMutex.Lock()
	for k, v := range sm.pendingChanges {
		allChanges[k] = v
	}
	sm.changesMutex.Unlock()
	
	// Add changes from handlers
	for dataType, handler := range sm.syncHandlers {
		changes, err := handler.GetLocalChanges()
		if err != nil {
			log.Printf("Failed to get local changes from handler %s: %v", dataType, err)
			continue
		}
		
		for k, v := range changes {
			allChanges[fmt.Sprintf("%s/%s", dataType, k)] = v
		}
	}
	
	// Upload each change to S3
	for key, data := range allChanges {
		s3Key := fmt.Sprintf("devices/%s/data/%s", sm.deviceID, key)
		
		_, err := sm.s3Client.PutObject(context.Background(), &s3.PutObjectInput{
			Bucket: aws.String(sm.syncBucket),
			Key:    aws.String(s3Key),
			Body:   aws.ReadSeekCloser(bytes.NewReader(data)),
			Metadata: map[string]string{
				"device-id":   sm.deviceID,
				"upload-time": time.Now().UTC().Format(time.RFC3339),
			},
		})
		
		if err != nil {
			return fmt.Errorf("failed to upload %s: %w", key, err)
		}
		
		// Remove from pending changes after successful upload
		sm.changesMutex.Lock()
		delete(sm.pendingChanges, key)
		sm.changesMutex.Unlock()
	}
	
	return nil
}

// downloadUpdates downloads updates from S3
func (sm *SyncManager) downloadUpdates() error {
	// Get the manifest file that lists all available updates
	manifestKey := fmt.Sprintf("devices/%s/manifest.json", sm.deviceID)
	
	result, err := sm.s3Client.GetObject(context.Background(), &s3.GetObjectInput{
		Bucket: aws.String(sm.syncBucket),
		Key:    aws.String(manifestKey),
	})
	
	if err != nil {
		// If manifest doesn't exist, that's okay
		log.Printf("No manifest found: %v", err)
		return nil
	}
	
	// Read and parse the manifest
	manifestData, err := ioutil.ReadAll(result.Body)
	if err != nil {
		return fmt.Errorf("failed to read manifest: %w", err)
	}
	
	var manifest struct {
		Updates []struct {
			Key       string    `json:"key"`
			Timestamp time.Time `json:"timestamp"`
			DataType  string    `json:"dataType"`
		} `json:"updates"`
	}
	
	if err := json.Unmarshal(manifestData, &manifest); err != nil {
		return fmt.Errorf("failed to parse manifest: %w", err)
	}
	
	// Process each update
	for _, update := range manifest.Updates {
		// Skip if we've already processed this update
		if !update.Timestamp.After(sm.lastSyncTime) {
			continue
		}
		
		// Download the update
		s3Key := fmt.Sprintf("devices/%s/updates/%s", sm.deviceID, update.Key)
		updateResult, err := sm.s3Client.GetObject(context.Background(), &s3.GetObjectInput{
			Bucket: aws.String(sm.syncBucket),
			Key:    aws.String(s3Key),
		})
		
		if err != nil {
			log.Printf("Failed to download update %s: %v", update.Key, err)
			continue
		}
		
		// Read the update data
		updateData, err := ioutil.ReadAll(updateResult.Body)
		if err != nil {
			log.Printf("Failed to read update %s: %v", update.Key, err)
			continue
		}
		
		// Save to local cache
		filePath := filepath.Join(sm.localCachePath, update.Key)
		if err := os.MkdirAll(filepath.Dir(filePath), 0755); err != nil {
			log.Printf("Failed to create directory for %s: %v", update.Key, err)
			continue
		}
		
		if err := ioutil.WriteFile(filePath, updateData, 0644); err != nil {
			log.Printf("Failed to write update %s to cache: %v", update.Key, err)
			continue
		}
		
		// Process with appropriate handler
		if handler, ok := sm.syncHandlers[update.DataType]; ok {
			if err := handler.ProcessUpdate(update.Key, updateData); err != nil {
				log.Printf("Handler failed to process update %s: %v", update.Key, err)
			}
		}
	}
	
	return nil
}

// Close closes the SyncManager and releases resources
func (sm *SyncManager) Close() error {
	sm.syncCron.Stop()
	return sm.db.Close()
}

// GetLastSyncTime returns the time of the last successful sync
func (sm *SyncManager) GetLastSyncTime() time.Time {
	return sm.lastSyncTime
}

// ForceSyncNow forces an immediate synchronization
func (sm *SyncManager) ForceSyncNow() error {
	return sm.Sync()
}

// GetSyncStatus returns the current sync status
func (sm *SyncManager) GetSyncStatus() map[string]interface{} {
	sm.changesMutex.Lock()
	pendingCount := len(sm.pendingChanges)
	sm.changesMutex.Unlock()
	
	sm.syncMux.Lock()
	inProgress := sm.syncInProgress
	sm.syncMux.Unlock()
	
	return map[string]interface{}{
		"last_sync_time":   sm.lastSyncTime,
		"is_online":        sm.IsOnline(),
		"sync_in_progress": inProgress,
		"pending_changes":  pendingCount,
		"device_id":        sm.deviceID,
	}
}
