"""
GTT Configuration Module
========================

Configuration settings for GTT order generation including:
- Support/Resistance calculation parameters
- Risk management settings  
- Position sizing rules
- Trigger value calculations
"""

class GTTConfig:
    """Configuration class for GTT order generation"""
    
    def __init__(self):
        # Support/Resistance Levels
        self.support_percentage = 5.0    # 5% below current price
        self.resistance_percentage = 8.0  # 8% above current price
        
        # Position Sizing for Two-Leg Orders
        self.sell_quantity_split = 0.75   # 75% of holding for first leg
        self.sell_quantity_split_second = 0.60  # 60% remaining for second leg
        
        # Buy Quantity (for fresh positions)
        self.buy_quantity_base = 100      # Base quantity for buy orders
        self.buy_quantity_split = 0.70    # 70% for first buy leg
        
        # Risk Management
        self.max_trigger_spread = 15.0    # Max % difference between trigger levels
        self.min_trigger_value = 50.0     # Minimum trigger value
        
        # GTT Order Settings
        self.default_type = "two-leg"
        self.default_status = "ACTIVE"
        self.default_exchange = "NSE"
        
        # Price Adjustment Factors
        self.support_buffer = 0.99        # 1% buffer below support
        self.resistance_buffer = 1.01     # 1% buffer above resistance
        
    def get_support_level(self, current_price):
        """Calculate support level based on current price"""
        support = current_price * (1 - self.support_percentage / 100)
        return max(support * self.support_buffer, self.min_trigger_value)
    
    def get_resistance_level(self, current_price):
        """Calculate resistance level based on current price"""
        return current_price * (1 + self.resistance_percentage / 100) * self.resistance_buffer
    
    def calculate_sell_quantities(self, total_holding):
        """Calculate sell quantities for two-leg GTT"""
        if total_holding <= 0:
            return 0, 0
            
        first_leg = int(total_holding * self.sell_quantity_split)
        remaining = total_holding - first_leg
        second_leg = int(remaining * self.sell_quantity_split_second)
        
        return first_leg, second_leg
    
    def calculate_buy_quantities(self, funds_available=None, stock_price=None):
        """Calculate buy quantities for two-leg GTT"""
        if funds_available and stock_price and stock_price > 0:
            max_shares = int(funds_available / stock_price)
            base_quantity = min(max_shares, self.buy_quantity_base * 2)
        else:
            base_quantity = self.buy_quantity_base
            
        first_leg = int(base_quantity * self.buy_quantity_split)
        second_leg = base_quantity - first_leg
        
        return first_leg, second_leg