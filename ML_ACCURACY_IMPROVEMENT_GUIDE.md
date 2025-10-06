# 🎯 ML Model Accuracy Improvement Guide

## 📊 Current Performance Analysis

### Test Set Results:
- **Train Accuracy**: 100% ⚠️ (Overfitting!)
- **Test Accuracy**: 39.62% (vs 33% random baseline)
- **Improvement over Random**: Only +6.62%

### Validation Set Results (20 predictions):
- **Exact Match Accuracy**: 15.0% (3/20) ❌
- **Directional Accuracy**: 15.0% (3/20) ❌  
- **Average Confidence**: 89.9% ⚠️ (Overconfident!)

### Production Results (36 stocks):
✅ **Working**: Model makes predictions with confidence 35-99%
✅ **Diverse Signals**: BUY (PFC 98%, RECLTD 94%, J&KBANK 79%)
❌ **Problem**: Predicts HOLD 95% of the time (too conservative)

---

## 🚀 10 Strategies to Improve ML Accuracy

### 1️⃣ **Collect More Training Data** (HIGH IMPACT - EASY)

**Current**: 265 samples from 50 stocks
**Target**: 1000-2000 samples from 100-150 stocks

**How to Implement**:
```python
# In train_ml_model.py main():
trainer = MLTrainer(lookback_days=180, forward_days=5)
symbols = trainer.load_stock_list()[:100]  # Change from 50 to 100 stocks
trainer.collect_training_data(symbols, num_samples_per_stock=15)  # Change from 10 to 15
```

**Expected Impact**: +5-10% accuracy
**Time to Implement**: 5 minutes
**Training Time**: 15-20 minutes

---

### 2️⃣ **Fix Class Imbalance** (HIGH IMPACT - MEDIUM)

**Current Distribution**:
- UP: 48 (18%)
- HOLD: 129 (49%)
- DOWN: 88 (33%)

**Problem**: Model predicts HOLD 95% because HOLD is most common

**Solutions**:

#### A. Use Class Weights:
```python
# In ml_predictor.py train_model() method:
from sklearn.utils.class_weight import compute_class_weight

# After splitting data, before training:
class_weights = compute_class_weight('balanced', 
                                     classes=np.unique(y_train), 
                                     y=y_train)
class_weight_dict = {i: w for i, w in zip(np.unique(y_train), class_weights)}

self.model = GradientBoostingClassifier(
    n_estimators=100,
    learning_rate=0.1,
    max_depth=5,
    random_state=42,
    class_weight=class_weight_dict  # Add this!
)
```

**Expected Impact**: +10-15% accuracy
**Time to Implement**: 10 minutes

#### B. Use SMOTE (Synthetic Minority Over-sampling):
```python
# Install: pip install imbalanced-learn
from imblearn.over_sampling import SMOTE

# In ml_predictor.py train_model():
smote = SMOTE(random_state=42)
X_train_balanced, y_train_balanced = smote.fit_resample(X_train, y_train)

# Then train on balanced data
self.model.fit(X_train_balanced, y_train_balanced)
```

**Expected Impact**: +15-20% accuracy
**Time to Implement**: 15 minutes

---

### 3️⃣ **Better Feature Engineering** (HIGH IMPACT - HARD)

**Current**: 65 features (basic technical + fundamentals)

**Add Advanced Features**:
```python
# In train_ml_model.py collect_historical_data():

# 1. Momentum indicators
stock_data['momentum_10d'] = (closes[-1] - closes[-10]) / closes[-10] * 100
stock_data['momentum_30d'] = (closes[-1] - closes[-30]) / closes[-30] * 100

# 2. Volatility ratios
stock_data['volatility_ratio'] = np.std(returns[-5:]) / np.std(returns[-20:])

# 3. Volume momentum
stock_data['volume_momentum'] = volumes[-1] / np.mean(volumes[-20:])

# 4. Price position
stock_data['price_position'] = (closes[-1] - np.min(closes[-20:])) / (np.max(closes[-20:]) - np.min(closes[-20:]))

# 5. Moving average convergence
stock_data['ma_20_50_conv'] = (stock_data['ma_20'] - stock_data['ma_50']) / stock_data['ma_50'] * 100

# 6. Relative strength to market
# (Need to fetch NIFTY data separately)
```

**Expected Impact**: +5-10% accuracy
**Time to Implement**: 1-2 hours

---

### 4️⃣ **Try Different Models** (MEDIUM IMPACT - EASY)

**Current**: GradientBoostingClassifier

**Test These Models**:

```python
# In ml_predictor.py train_model():

# Option 1: Random Forest
from sklearn.ensemble import RandomForestClassifier
self.model = RandomForestClassifier(
    n_estimators=200,
    max_depth=10,
    min_samples_split=5,
    class_weight='balanced',
    random_state=42
)

# Option 2: XGBoost (Install: pip install xgboost)
import xgboost as xgb
self.model = xgb.XGBClassifier(
    n_estimators=150,
    learning_rate=0.1,
    max_depth=6,
    scale_pos_weight=2,  # For class imbalance
    random_state=42
)

# Option 3: LightGBM (Install: pip install lightgbm)
import lightgbm as lgb
self.model = lgb.LGBMClassifier(
    n_estimators=150,
    learning_rate=0.1,
    max_depth=6,
    class_weight='balanced',
    random_state=42
)

# Option 4: Ensemble (Voting)
from sklearn.ensemble import VotingClassifier
gb = GradientBoostingClassifier(...)
rf = RandomForestClassifier(...)
xgb_model = xgb.XGBClassifier(...)

self.model = VotingClassifier(
    estimators=[('gb', gb), ('rf', rf), ('xgb', xgb_model)],
    voting='soft'
)
```

**Expected Impact**: +5-15% accuracy (XGBoost/LightGBM usually best)
**Time to Implement**: 20-30 minutes

---

### 5️⃣ **Hyperparameter Tuning** (MEDIUM IMPACT - MEDIUM)

**Use GridSearchCV or RandomizedSearchCV**:

```python
# In ml_predictor.py train_model():
from sklearn.model_selection import RandomizedSearchCV

param_distributions = {
    'n_estimators': [100, 150, 200, 250],
    'learning_rate': [0.05, 0.1, 0.15, 0.2],
    'max_depth': [3, 4, 5, 6, 7],
    'min_samples_split': [2, 5, 10],
    'min_samples_leaf': [1, 2, 4]
}

base_model = GradientBoostingClassifier(random_state=42)

search = RandomizedSearchCV(
    base_model,
    param_distributions,
    n_iter=50,  # Try 50 combinations
    cv=5,  # 5-fold cross-validation
    scoring='accuracy',
    n_jobs=-1,
    random_state=42
)

search.fit(X_train, y_train)
self.model = search.best_estimator_

print(f"Best parameters: {search.best_params_}")
print(f"Best CV score: {search.best_score_:.2%}")
```

**Expected Impact**: +3-8% accuracy
**Time to Implement**: 30 minutes
**Tuning Time**: 20-30 minutes

---

### 6️⃣ **Adjust Prediction Thresholds** (MEDIUM IMPACT - EASY)

**Problem**: Model uses 33% threshold for each class (UP/HOLD/DOWN)

**Solution**: Adjust thresholds based on class probabilities

```python
# In ml_predictor.py predict_price_movement():

# Get class probabilities
proba = self.model.predict_proba(features_scaled)[0]
# proba = [prob_DOWN, prob_HOLD, prob_UP]

# Custom thresholds (tune these)
THRESHOLD_UP = 0.40    # Easier to predict UP
THRESHOLD_DOWN = 0.40  # Easier to predict DOWN
THRESHOLD_HOLD = 0.20  # Harder to predict HOLD

if proba[2] > THRESHOLD_UP:  # UP class
    prediction = 1
    confidence = proba[2] * 100
elif proba[0] > THRESHOLD_DOWN:  # DOWN class
    prediction = -1
    confidence = proba[0] * 100
else:  # HOLD
    prediction = 0
    confidence = proba[1] * 100
```

**Expected Impact**: +5-10% accuracy
**Time to Implement**: 15 minutes

---

### 7️⃣ **Use Better Labels** (HIGH IMPACT - MEDIUM)

**Current**: 3 classes (UP +2%, HOLD ±2%, DOWN -2%)

**Alternative Labeling Strategies**:

#### A. Binary Classification (Easier):
```python
# In train_ml_model.py:
if price_return > 0:
    label = 1  # UP
else:
    label = 0  # DOWN
# Remove HOLD class entirely
```

#### B. Different Thresholds:
```python
# Try more aggressive thresholds
if price_return > 5.0:  # UP (was 2%)
    label = 1
elif price_return < -5.0:  # DOWN (was -2%)
    label = -1
else:
    label = 0  # HOLD
```

#### C. Weighted Returns:
```python
# Weight by volatility
volatility = np.std(returns[-20:])
adjusted_return = price_return / volatility

if adjusted_return > 0.5:
    label = 1
elif adjusted_return < -0.5:
    label = -1
else:
    label = 0
```

**Expected Impact**: +10-20% accuracy
**Time to Implement**: 30 minutes

---

### 8️⃣ **Add Time-Based Features** (MEDIUM IMPACT - MEDIUM)

**Day of Week, Month Effects**:

```python
# In train_ml_model.py collect_historical_data():

stock_data['day_of_week'] = sample_date.weekday()  # 0=Monday, 4=Friday
stock_data['month'] = sample_date.month
stock_data['quarter'] = (sample_date.month - 1) // 3 + 1
stock_data['days_since_earnings'] = 30  # Would need earnings data
stock_data['is_month_end'] = 1 if sample_date.day >= 25 else 0
```

**Expected Impact**: +3-5% accuracy
**Time to Implement**: 20 minutes

---

### 9️⃣ **Cross-Validation During Training** (LOW IMPACT - EASY)

**Better evaluation of model performance**:

```python
# In ml_predictor.py train_model():
from sklearn.model_selection import cross_val_score

# Before final training
cv_scores = cross_val_score(
    self.model, 
    X_train, 
    y_train, 
    cv=5,  # 5-fold
    scoring='accuracy'
)

print(f"CV Accuracy: {cv_scores.mean():.2%} (+/- {cv_scores.std() * 2:.2%})")

# Then train on full data
self.model.fit(X_train, y_train)
```

**Expected Impact**: Better understanding of true performance
**Time to Implement**: 10 minutes

---

### 🔟 **Ensemble Multiple Forward Days** (HIGH IMPACT - HARD)

**Current**: Predict 5 days ahead only

**Better**: Predict 3, 5, 10 days and ensemble

```python
# Train 3 separate models
model_3d = train_model(forward_days=3)
model_5d = train_model(forward_days=5)  
model_10d = train_model(forward_days=10)

# Combine predictions with weighted voting
pred_3d = model_3d.predict(features)
pred_5d = model_5d.predict(features)
pred_10d = model_10d.predict(features)

# Weight short-term more
final_pred = (pred_3d * 0.5 + pred_5d * 0.3 + pred_10d * 0.2)
```

**Expected Impact**: +8-12% accuracy
**Time to Implement**: 1-2 hours

---

## 🎯 **Recommended Implementation Order**

### **Phase 1: Quick Wins (1-2 hours)**
1. ✅ Add class weights (Strategy #2A)
2. ✅ Collect more data - 100 stocks, 15 samples each (Strategy #1)
3. ✅ Adjust prediction thresholds (Strategy #6)

**Expected Total Impact**: +20-35% accuracy

### **Phase 2: Medium Effort (3-4 hours)**
4. Try XGBoost/LightGBM (Strategy #4)
5. Use SMOTE for class balance (Strategy #2B)
6. Add momentum features (Strategy #3)

**Expected Total Impact**: +30-50% accuracy

### **Phase 3: Advanced (1-2 days)**
7. Hyperparameter tuning (Strategy #5)
8. Try binary classification (Strategy #7)
9. Add time features (Strategy #8)
10. Multi-timeframe ensemble (Strategy #10)

**Expected Total Impact**: +40-60% accuracy

---

## 📊 **Expected Final Performance**

### After Phase 1:
- Test Accuracy: 50-60%
- Validation Accuracy: 40-50%
- Production: More balanced predictions

### After Phase 2:
- Test Accuracy: 60-70%
- Validation Accuracy: 50-60%
- Production: High-confidence predictions

### After Phase 3:
- Test Accuracy: 65-75%
- Validation Accuracy: 55-65%
- Production: Reliable trading signals

---

## 🛠️ **Quick Implementation Script**

Create `train_ml_model_improved.py`:

```python
"""
Improved ML Training with Better Accuracy
Run: python train_ml_model_improved.py
"""

# Strategy #1: More data
symbols = trainer.load_stock_list()[:100]  # 100 stocks instead of 50
trainer.collect_training_data(symbols, num_samples_per_stock=15)  # 15 samples instead of 10

# Strategy #2A: Class weights
from sklearn.utils.class_weight import compute_class_weight

class_weights = compute_class_weight('balanced', 
                                     classes=np.unique(y_train), 
                                     y=y_train)
class_weight_dict = {i: w for i, w in zip(np.unique(y_train), class_weights)}

# Strategy #4: Try XGBoost
import xgboost as xgb
self.model = xgb.XGBClassifier(
    n_estimators=200,
    learning_rate=0.1,
    max_depth=6,
    scale_pos_weight=class_weight_dict[1],  # Handle imbalance
    random_state=42
)

# Train with cross-validation
from sklearn.model_selection import cross_val_score
cv_scores = cross_val_score(self.model, X_train, y_train, cv=5)
print(f"CV Accuracy: {cv_scores.mean():.2%}")

# Final training
self.model.fit(X_train, y_train)
```

---

## 📈 **Monitoring & Iteration**

After each improvement:
1. **Retrain**: `python train_ml_model_improved.py`
2. **Validate**: `python validate_ml_model.py`
3. **Test Production**: `python analyze_top200_stocks_enhanced.py -n 10 -b 5`
4. **Compare**: Check validation_results.csv for improvements
5. **Iterate**: Try next strategy

**Track metrics**:
- Test accuracy
- Validation accuracy  
- Class-wise precision/recall
- Confidence calibration
- Production prediction distribution

---

## 🎓 **Learning Resources**

- **Imbalanced Learning**: https://imbalanced-learn.org/stable/
- **XGBoost**: https://xgboost.readthedocs.io/
- **Feature Engineering**: https://www.kaggle.com/learn/feature-engineering
- **Hyperparameter Tuning**: https://scikit-learn.org/stable/modules/grid_search.html

---

**Good luck improving your ML model! Start with Phase 1 for quick wins! 🚀**
