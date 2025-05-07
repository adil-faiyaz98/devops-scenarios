"""
Inventory Optimization Model for E-commerce Platform.

This module implements an inventory optimization model that predicts
demand, optimizes stock levels, and provides reorder recommendations.

Key features:
- Time series forecasting for demand prediction
- Multi-echelon inventory optimization
- Seasonal trend analysis
- Safety stock calculation
- Reorder point determination
- Lead time prediction
"""

import os
import json
import pickle
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Union, Any
from prophet import Prophet
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler


class InventoryOptimizer:
    """
    Inventory optimization model for e-commerce platform.
    
    This class implements multiple techniques to optimize inventory
    levels and provide reorder recommendations.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the inventory optimizer.
        
        Args:
            config: Configuration dictionary with model parameters
        """
        self.config = config or {}
        
        # Default configuration
        self.default_config = {
            "forecast_horizon": 90,  # Days to forecast
            "safety_stock_z_value": 1.96,  # Z-value for 95% service level
            "min_safety_stock_days": 7,  # Minimum safety stock in days
            "max_safety_stock_days": 30,  # Maximum safety stock in days
            "prophet": {
                "changepoint_prior_scale": 0.05,
                "seasonality_prior_scale": 10.0,
                "seasonality_mode": "multiplicative",
                "interval_width": 0.95
            },
            "random_forest": {
                "n_estimators": 100,
                "max_depth": 10,
                "random_state": 42
            }
        }
        
        # Merge default config with provided config
        for key, default_value in self.default_config.items():
            if key not in self.config:
                self.config[key] = default_value
            elif isinstance(default_value, dict):
                for subkey, subvalue in default_value.items():
                    if subkey not in self.config[key]:
                        self.config[key][subkey] = subvalue
        
        # Initialize models
        self.demand_models = {}  # Prophet models for demand forecasting
        self.lead_time_model = None  # Random Forest for lead time prediction
        self.scaler = None  # Scaler for lead time features
        
        # Initialize product data
        self.product_data = {}
    
    def fit_demand_models(self, sales_data: pd.DataFrame) -> None:
        """
        Fit demand forecasting models for each product.
        
        Args:
            sales_data: DataFrame with sales data
                Must have columns: date, product_id, quantity
        """
        if sales_data.empty:
            raise ValueError("Empty data provided for fitting")
        
        # Ensure required columns exist
        required_columns = ["date", "product_id", "quantity"]
        if not all(col in sales_data.columns for col in required_columns):
            missing = [col for col in required_columns if col not in sales_data.columns]
            raise ValueError(f"Missing required columns: {missing}")
        
        # Convert date to datetime if it's not already
        if not pd.api.types.is_datetime64_any_dtype(sales_data["date"]):
            sales_data["date"] = pd.to_datetime(sales_data["date"])
        
        # Group by product_id and date
        grouped = sales_data.groupby(["product_id", "date"]).agg({"quantity": "sum"}).reset_index()
        
        # Fit Prophet models for each product
        for product_id, group in grouped.groupby("product_id"):
            # Prepare data for Prophet
            prophet_data = group[["date", "quantity"]].copy()
            prophet_data.columns = ["ds", "y"]
            
            # Sort by date
            prophet_data = prophet_data.sort_values("ds")
            
            # Initialize and fit Prophet model
            prophet_config = self.config["prophet"]
            model = Prophet(
                changepoint_prior_scale=prophet_config["changepoint_prior_scale"],
                seasonality_prior_scale=prophet_config["seasonality_prior_scale"],
                seasonality_mode=prophet_config["seasonality_mode"],
                interval_width=prophet_config["interval_width"]
            )
            
            # Add weekly and yearly seasonality
            model.add_seasonality(name='weekly', period=7, fourier_order=3)
            if len(prophet_data) >= 365:  # At least 1 year of data
                model.add_seasonality(name='yearly', period=365.25, fourier_order=10)
            
            # Fit the model
            try:
                model.fit(prophet_data)
                self.demand_models[product_id] = model
            except Exception as e:
                logging.error(f"Failed to fit Prophet model for product {product_id}: {str(e)}")
    
    def fit_lead_time_model(self, order_data: pd.DataFrame) -> None:
        """
        Fit lead time prediction model.
        
        Args:
            order_data: DataFrame with order data
                Must have columns: order_date, delivery_date, product_id, supplier_id, quantity
        """
        if order_data.empty:
            raise ValueError("Empty data provided for fitting")
        
        # Ensure required columns exist
        required_columns = ["order_date", "delivery_date", "product_id", "supplier_id", "quantity"]
        if not all(col in order_data.columns for col in required_columns):
            missing = [col for col in required_columns if col not in order_data.columns]
            raise ValueError(f"Missing required columns: {missing}")
        
        # Convert dates to datetime if they're not already
        for col in ["order_date", "delivery_date"]:
            if not pd.api.types.is_datetime64_any_dtype(order_data[col]):
                order_data[col] = pd.to_datetime(order_data[col])
        
        # Calculate lead time in days
        order_data["lead_time_days"] = (order_data["delivery_date"] - order_data["order_date"]).dt.days
        
        # Filter out invalid lead times
        order_data = order_data[order_data["lead_time_days"] > 0]
        
        # Prepare features for lead time prediction
        features = pd.get_dummies(order_data[["product_id", "supplier_id"]], drop_first=True)
        features["quantity"] = order_data["quantity"]
        features["month"] = order_data["order_date"].dt.month
        features["day_of_week"] = order_data["order_date"].dt.dayofweek
        
        # Add any additional features from order_data
        additional_features = [
            "distance_km", "is_international", "shipping_method", "priority"
        ]
        for feature in additional_features:
            if feature in order_data.columns:
                if pd.api.types.is_categorical_dtype(order_data[feature]):
                    # One-hot encode categorical features
                    dummies = pd.get_dummies(order_data[feature], prefix=feature, drop_first=True)
                    features = pd.concat([features, dummies], axis=1)
                else:
                    features[feature] = order_data[feature]
        
        # Scale features
        self.scaler = StandardScaler()
        X = self.scaler.fit_transform(features)
        y = order_data["lead_time_days"].values
        
        # Fit Random Forest model
        rf_config = self.config["random_forest"]
        self.lead_time_model = RandomForestRegressor(
            n_estimators=rf_config["n_estimators"],
            max_depth=rf_config["max_depth"],
            random_state=rf_config["random_state"]
        )
        self.lead_time_model.fit(X, y)
    
    def set_product_data(self, product_data: Dict[str, Dict[str, Any]]) -> None:
        """
        Set product data for inventory optimization.
        
        Args:
            product_data: Dictionary mapping product_id to product data
                Each product data dictionary should have:
                - cost: Product cost
                - price: Product price
                - holding_cost_pct: Holding cost as percentage of product cost
                - stockout_cost: Cost of stockout
                - min_order_quantity: Minimum order quantity
                - supplier_id: Supplier ID
                - current_stock: Current stock level
                - reorder_point: Current reorder point
                - safety_stock: Current safety stock
        """
        self.product_data = product_data
    
    def forecast_demand(self, product_id: str, days: Optional[int] = None) -> Dict[str, Any]:
        """
        Forecast demand for a product.
        
        Args:
            product_id: Product ID
            days: Number of days to forecast (default: from config)
            
        Returns:
            Dictionary with forecast results
        """
        if days is None:
            days = self.config["forecast_horizon"]
        
        if product_id not in self.demand_models:
            return {
                "product_id": product_id,
                "success": False,
                "error": "No demand model available for this product"
            }
        
        # Get model
        model = self.demand_models[product_id]
        
        # Create future dataframe
        future = model.make_future_dataframe(periods=days)
        
        # Make forecast
        forecast = model.predict(future)
        
        # Extract forecast data
        forecast_data = []
        for _, row in forecast.iloc[-days:].iterrows():
            forecast_data.append({
                "date": row["ds"].strftime("%Y-%m-%d"),
                "demand": max(0, round(row["yhat"])),
                "demand_lower": max(0, round(row["yhat_lower"])),
                "demand_upper": max(0, round(row["yhat_upper"]))
            })
        
        # Calculate summary statistics
        total_demand = sum(item["demand"] for item in forecast_data)
        avg_daily_demand = total_demand / days
        max_daily_demand = max(item["demand"] for item in forecast_data)
        
        # Calculate demand variability
        demand_values = [item["demand"] for item in forecast_data]
        demand_std = np.std(demand_values)
        demand_cv = demand_std / avg_daily_demand if avg_daily_demand > 0 else 0
        
        return {
            "product_id": product_id,
            "success": True,
            "forecast_days": days,
            "total_demand": total_demand,
            "avg_daily_demand": avg_daily_demand,
            "max_daily_demand": max_daily_demand,
            "demand_std": demand_std,
            "demand_cv": demand_cv,
            "forecast": forecast_data
        }
    
    def predict_lead_time(self, product_id: str, supplier_id: str, quantity: int, **kwargs) -> Dict[str, Any]:
        """
        Predict lead time for a product order.
        
        Args:
            product_id: Product ID
            supplier_id: Supplier ID
            quantity: Order quantity
            **kwargs: Additional features for lead time prediction
            
        Returns:
            Dictionary with lead time prediction results
        """
        if self.lead_time_model is None or self.scaler is None:
            return {
                "product_id": product_id,
                "supplier_id": supplier_id,
                "success": False,
                "error": "No lead time model available"
            }
        
        # Prepare features
        features = {}
        
        # One-hot encode product_id and supplier_id
        # In a real implementation, this would need to match the training data encoding
        features[f"product_id_{product_id}"] = 1
        features[f"supplier_id_{supplier_id}"] = 1
        
        # Add quantity
        features["quantity"] = quantity
        
        # Add current month and day of week
        current_date = pd.Timestamp.now()
        features["month"] = current_date.month
        features["day_of_week"] = current_date.dayofweek
        
        # Add additional features
        for key, value in kwargs.items():
            features[key] = value
        
        # Convert to DataFrame and ensure all columns from training are present
        features_df = pd.DataFrame([features])
        
        # Scale features
        # In a real implementation, we would need to ensure the feature columns match the training data
        X = self.scaler.transform(features_df)
        
        # Predict lead time
        lead_time = self.lead_time_model.predict(X)[0]
        
        # Round to nearest day and ensure positive
        lead_time_days = max(1, round(lead_time))
        
        return {
            "product_id": product_id,
            "supplier_id": supplier_id,
            "quantity": quantity,
            "success": True,
            "lead_time_days": lead_time_days
        }
    
    def calculate_safety_stock(self, product_id: str, lead_time_days: int) -> Dict[str, Any]:
        """
        Calculate safety stock for a product.
        
        Args:
            product_id: Product ID
            lead_time_days: Lead time in days
            
        Returns:
            Dictionary with safety stock calculation results
        """
        # Get demand forecast
        forecast = self.forecast_demand(product_id)
        if not forecast["success"]:
            return {
                "product_id": product_id,
                "success": False,
                "error": forecast["error"]
            }
        
        # Get demand statistics
        avg_daily_demand = forecast["avg_daily_demand"]
        demand_std = forecast["demand_std"]
        
        # Calculate safety stock
        z = self.config["safety_stock_z_value"]
        safety_stock = z * demand_std * np.sqrt(lead_time_days)
        
        # Ensure safety stock is within reasonable limits
        min_safety_stock = avg_daily_demand * self.config["min_safety_stock_days"]
        max_safety_stock = avg_daily_demand * self.config["max_safety_stock_days"]
        
        safety_stock = max(min_safety_stock, min(safety_stock, max_safety_stock))
        
        # Round to integer
        safety_stock = round(safety_stock)
        
        return {
            "product_id": product_id,
            "success": True,
            "safety_stock": safety_stock,
            "avg_daily_demand": avg_daily_demand,
            "demand_std": demand_std,
            "lead_time_days": lead_time_days,
            "z_value": z,
            "min_safety_stock": min_safety_stock,
            "max_safety_stock": max_safety_stock
        }
    
    def calculate_reorder_point(self, product_id: str, lead_time_days: int) -> Dict[str, Any]:
        """
        Calculate reorder point for a product.
        
        Args:
            product_id: Product ID
            lead_time_days: Lead time in days
            
        Returns:
            Dictionary with reorder point calculation results
        """
        # Calculate safety stock
        safety_stock_result = self.calculate_safety_stock(product_id, lead_time_days)
        if not safety_stock_result["success"]:
            return {
                "product_id": product_id,
                "success": False,
                "error": safety_stock_result["error"]
            }
        
        # Get demand statistics
        avg_daily_demand = safety_stock_result["avg_daily_demand"]
        safety_stock = safety_stock_result["safety_stock"]
        
        # Calculate reorder point
        reorder_point = round(avg_daily_demand * lead_time_days + safety_stock)
        
        return {
            "product_id": product_id,
            "success": True,
            "reorder_point": reorder_point,
            "safety_stock": safety_stock,
            "avg_daily_demand": avg_daily_demand,
            "lead_time_days": lead_time_days,
            "lead_time_demand": round(avg_daily_demand * lead_time_days)
        }
    
    def calculate_economic_order_quantity(self, product_id: str) -> Dict[str, Any]:
        """
        Calculate economic order quantity (EOQ) for a product.
        
        Args:
            product_id: Product ID
            
        Returns:
            Dictionary with EOQ calculation results
        """
        # Get product data
        if product_id not in self.product_data:
            return {
                "product_id": product_id,
                "success": False,
                "error": "No product data available"
            }
        
        product = self.product_data[product_id]
        
        # Get demand forecast
        forecast = self.forecast_demand(product_id)
        if not forecast["success"]:
            return {
                "product_id": product_id,
                "success": False,
                "error": forecast["error"]
            }
        
        # Get annual demand
        annual_demand = forecast["avg_daily_demand"] * 365
        
        # Get order cost and holding cost
        order_cost = product.get("order_cost", 100)  # Default $100 if not provided
        holding_cost_pct = product.get("holding_cost_pct", 0.25)  # Default 25% if not provided
        holding_cost = product["cost"] * holding_cost_pct
        
        # Calculate EOQ
        eoq = np.sqrt((2 * annual_demand * order_cost) / holding_cost)
        
        # Round to integer and ensure minimum order quantity
        min_order_quantity = product.get("min_order_quantity", 1)
        eoq = max(min_order_quantity, round(eoq))
        
        return {
            "product_id": product_id,
            "success": True,
            "eoq": eoq,
            "annual_demand": annual_demand,
            "order_cost": order_cost,
            "holding_cost": holding_cost,
            "min_order_quantity": min_order_quantity
        }
    
    def get_inventory_recommendations(self, product_id: str) -> Dict[str, Any]:
        """
        Get inventory recommendations for a product.
        
        Args:
            product_id: Product ID
            
        Returns:
            Dictionary with inventory recommendations
        """
        # Get product data
        if product_id not in self.product_data:
            return {
                "product_id": product_id,
                "success": False,
                "error": "No product data available"
            }
        
        product = self.product_data[product_id]
        
        # Get supplier ID
        supplier_id = product.get("supplier_id")
        if not supplier_id:
            return {
                "product_id": product_id,
                "success": False,
                "error": "No supplier ID available"
            }
        
        # Calculate EOQ
        eoq_result = self.calculate_economic_order_quantity(product_id)
        if not eoq_result["success"]:
            return {
                "product_id": product_id,
                "success": False,
                "error": eoq_result["error"]
            }
        
        # Predict lead time
        lead_time_result = self.predict_lead_time(product_id, supplier_id, eoq_result["eoq"])
        if not lead_time_result["success"]:
            return {
                "product_id": product_id,
                "success": False,
                "error": lead_time_result["error"]
            }
        
        # Calculate reorder point
        reorder_point_result = self.calculate_reorder_point(product_id, lead_time_result["lead_time_days"])
        if not reorder_point_result["success"]:
            return {
                "product_id": product_id,
                "success": False,
                "error": reorder_point_result["error"]
            }
        
        # Get current stock level
        current_stock = product.get("current_stock", 0)
        
        # Determine if reorder is needed
        reorder_needed = current_stock <= reorder_point_result["reorder_point"]
        
        # Calculate days of supply
        avg_daily_demand = reorder_point_result["avg_daily_demand"]
        days_of_supply = current_stock / avg_daily_demand if avg_daily_demand > 0 else float('inf')
        
        # Calculate order quantity
        order_quantity = eoq_result["eoq"] if reorder_needed else 0
        
        # Calculate order cost
        order_cost = order_quantity * product["cost"] if reorder_needed else 0
        
        return {
            "product_id": product_id,
            "success": True,
            "current_stock": current_stock,
            "reorder_point": reorder_point_result["reorder_point"],
            "safety_stock": reorder_point_result["safety_stock"],
            "eoq": eoq_result["eoq"],
            "lead_time_days": lead_time_result["lead_time_days"],
            "avg_daily_demand": avg_daily_demand,
            "days_of_supply": round(days_of_supply, 1),
            "reorder_needed": reorder_needed,
            "order_quantity": order_quantity,
            "order_cost": order_cost,
            "supplier_id": supplier_id
        }
    
    def save(self, path: str) -> None:
        """
        Save the model to disk.
        
        Args:
            path: Directory path to save the model
        """
        os.makedirs(path, exist_ok=True)
        
        # Save demand models
        os.makedirs(os.path.join(path, "demand_models"), exist_ok=True)
        for product_id, model in self.demand_models.items():
            model_path = os.path.join(path, "demand_models", f"{product_id}.json")
            with open(model_path, "w") as f:
                json.dump(model.to_json(), f)
        
        # Save lead time model
        if self.lead_time_model is not None:
            with open(os.path.join(path, "lead_time_model.pkl"), "wb") as f:
                pickle.dump(self.lead_time_model, f)
        
        # Save scaler
        if self.scaler is not None:
            with open(os.path.join(path, "scaler.pkl"), "wb") as f:
                pickle.dump(self.scaler, f)
        
        # Save product data
        with open(os.path.join(path, "product_data.json"), "w") as f:
            json.dump(self.product_data, f)
        
        # Save config
        with open(os.path.join(path, "config.json"), "w") as f:
            json.dump(self.config, f)
    
    @classmethod
    def load(cls, path: str) -> "InventoryOptimizer":
        """
        Load the model from disk.
        
        Args:
            path: Directory path to load the model from
            
        Returns:
            Loaded InventoryOptimizer instance
        """
        # Load config
        with open(os.path.join(path, "config.json"), "r") as f:
            config = json.load(f)
        
        # Create instance
        optimizer = cls(config)
        
        # Load demand models
        demand_models_dir = os.path.join(path, "demand_models")
        if os.path.exists(demand_models_dir):
            for file_name in os.listdir(demand_models_dir):
                if file_name.endswith(".json"):
                    product_id = file_name[:-5]  # Remove .json extension
                    model_path = os.path.join(demand_models_dir, file_name)
                    
                    with open(model_path, "r") as f:
                        model_json = json.load(f)
                    
                    model = Prophet.from_json(model_json)
                    optimizer.demand_models[product_id] = model
        
        # Load lead time model
        if os.path.exists(os.path.join(path, "lead_time_model.pkl")):
            with open(os.path.join(path, "lead_time_model.pkl"), "rb") as f:
                optimizer.lead_time_model = pickle.load(f)
        
        # Load scaler
        if os.path.exists(os.path.join(path, "scaler.pkl")):
            with open(os.path.join(path, "scaler.pkl"), "rb") as f:
                optimizer.scaler = pickle.load(f)
        
        # Load product data
        if os.path.exists(os.path.join(path, "product_data.json")):
            with open(os.path.join(path, "product_data.json"), "r") as f:
                optimizer.product_data = json.load(f)
        
        return optimizer
