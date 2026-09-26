from copy import deepcopy
from typing import Any, Dict, List, Optional

DATA_SCIENCE_COURSE_ID = "SE-DSP-001"
DATA_SCIENCE_CURRICULUM_VERSION = "1.0"

# Detailed module knowledge. Topics are kept as source-backed curriculum items.
MODULES = [
    {"number": 1, "title": "Data Science Mindset & Real-World Problem Solving", "hours": 3,
     "topics": ["Data Science Foundations", "Problem Solving & Analytical Thinking", "Data Understanding", "Data Science Workflow"],
     "practical": "Think Like a Data Scientist Challenge"},
    {"number": 2, "title": "Python Programming for Data Science", "hours": 7,
     "topics": ["Python Fundamentals", "Data Structures", "Functions", "Modules, Packages, Exceptions, Files and Debugging", "Object-Oriented Programming"],
     "practical": "Python Data Processing System"},
    {"number": 3, "title": "SQL & Data Extraction", "hours": 5,
     "topics": ["Database Fundamentals", "SQL Fundamentals", "SQL Functions", "SQL Joins", "Advanced SQL Foundations"],
     "practical": "Business Data Investigation"},
    {"number": 4, "title": "NumPy & Pandas", "hours": 6,
     "topics": ["NumPy", "Pandas", "Data Manipulation"],
     "practical": "Messy Dataset Rescue"},
    {"number": 5, "title": "Data Cleaning & Data Quality", "hours": 5,
     "topics": ["Data Quality", "Data Preparation", "Machine Learning Data Safety"],
     "practical": "Data Quality Report"},
    {"number": 6, "title": "EDA & Data Visualization", "hours": 5,
     "topics": ["Exploratory Data Analysis", "Visualization", "Analytical Communication"],
     "practical": "Exploratory Data Investigation"},
    {"number": 7, "title": "Statistics & Probability for Data Science", "hours": 5,
     "topics": ["Descriptive Statistics", "Probability", "Inferential Statistics", "Covariance, Correlation and Causation"],
     "practical": "Statistical Analysis using Python"},
    {"number": 8, "title": "Machine Learning Foundations", "hours": 3,
     "topics": ["Machine Learning Concepts", "Model Behavior", "ML Workflow"],
     "practical": "Basic ML Workflow"},
    {"number": 9, "title": "Supervised Machine Learning", "hours": 7,
     "topics": ["Regression", "Classification", "Regression Evaluation", "Classification Evaluation", "Model Improvement"],
     "practical": "Predictive Machine Learning Project"},
    {"number": 10, "title": "Unsupervised Learning & Feature Engineering", "hours": 4,
     "topics": ["Clustering", "Dimensionality Reduction", "Feature Engineering", "Practical Application"],
     "practical": "Segmentation / Unsupervised Learning Project"},
    {"number": 11, "title": "Deep Learning & Neural Networks", "hours": 3,
     "topics": ["Neural Network Foundations", "Training", "TensorFlow and Keras", "Deep Learning Concepts"],
     "practical": "Basic Neural Network Implementation"},
    {"number": 12, "title": "NLP Fundamentals", "hours": 2,
     "topics": ["NLP Foundations", "Text Representation", "Practical NLP"],
     "practical": "NLP Mini Project"},
    {"number": 13, "title": "Model Evaluation, MLOps & Deployment", "hours": 3,
     "topics": ["Model Evaluation", "MLOps Fundamentals", "Deployment"],
     "practical": "Model Deployment Project"},
    {"number": 14, "title": "Projects, Portfolio & Data Science Career Lab", "hours": 2,
     "topics": ["Portfolio", "Career Preparation"],
     "practical": "End-to-End Data Science Project"},
]

TOPIC_DETAILS = {
    1: ["What is Data Science?", "Data Science vs Data Analytics", "Data Science vs AI", "Data Science vs Machine Learning", "Data Science lifecycle", "Structured and unstructured data", "Real-world applications", "Role of a Data Scientist", "Tools and technologies overview", "Ethics in Data Science", "Problem framing", "Defining objectives", "Defining success metrics", "Data quality", "Data bias", "Data leakage", "Reproducibility", "Responsible Data Science"],
    2: ["Variables", "Data types", "Operators", "Input and output", "Conditional statements", "Loops", "Strings", "Lists", "Tuples", "Dictionaries", "Sets", "Comprehensions", "Functions", "Parameters", "Return values", "Lambda functions", "Scope", "Modules", "Packages", "Exception handling", "File handling", "CSV", "JSON", "Debugging", "Classes", "Objects", "Methods", "Constructors", "Basic inheritance concepts"],
    3: ["Databases", "Tables", "Rows", "Columns", "Primary keys", "Foreign keys", "Relationships", "Relational databases", "SELECT", "WHERE", "DISTINCT", "ORDER BY", "LIMIT", "Aggregate functions", "GROUP BY", "HAVING", "CASE", "NULL handling", "String functions", "Date functions", "INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "FULL JOIN concept", "Multi-table analysis", "Subqueries", "CTE introduction", "Window functions", "Ranking", "Running totals"],
    4: ["Arrays", "Dimensions", "Indexing", "Slicing", "Vectorized operations", "Broadcasting", "Mathematical operations", "Numerical computation", "Basic linear algebra concepts", "Series", "DataFrames", "Filtering", "Sorting", "Grouping", "Aggregation", "Merge", "Join", "Concatenation", "Pivoting", "Missing values", "Data type conversion", "Date handling", "Data transformation", "Derived columns", "Feature creation"],
    5: ["Data quality dimensions", "Missing data", "Duplicate data", "Invalid values", "Incorrect data types", "Inconsistent categories", "Outliers", "Impossible values", "Standardization", "Normalization", "Transformation", "Encoding", "Validation", "Data quality checks", "Data leakage", "Train/test contamination", "Preventing invalid transformations"],
    6: ["Univariate analysis", "Bivariate analysis", "Multivariate analysis", "Distribution analysis", "Trend analysis", "Correlation analysis", "Segmentation", "Outlier investigation", "Pattern discovery", "Anomaly investigation", "Matplotlib", "Seaborn", "Bar charts", "Line charts", "Histograms", "Scatter plots", "Box plots", "Heatmaps", "Distribution plots", "Pair plots", "Chart selection", "Communicating findings"],
    7: ["Mean", "Median", "Mode", "Range", "Variance", "Standard deviation", "Percentiles", "Quartiles", "IQR", "Probability fundamentals", "Conditional probability", "Independence", "Basic distributions", "Population", "Sample", "Sampling", "Confidence intervals", "Hypothesis testing", "Null hypothesis", "Alternative hypothesis", "p-value interpretation", "Covariance", "Correlation", "Correlation vs causation"],
    8: ["Supervised learning", "Unsupervised learning", "Features", "Target", "Training", "Validation", "Testing", "Generalization", "Overfitting", "Underfitting", "Bias", "Variance", "Bias/variance trade-off", "Train/test split", "Baseline models", "Feature selection", "Feature engineering", "Cross-validation", "Data leakage", "Model evaluation"],
    9: ["Linear Regression", "Multiple Regression", "Polynomial Regression", "Ridge Regression", "Lasso Regression", "Logistic Regression", "Decision Trees", "Random Forest", "K-Nearest Neighbors", "Support Vector Machines", "Naive Bayes", "MAE", "MSE", "RMSE", "R²", "Accuracy", "Precision", "Recall", "F1-score", "Confusion Matrix", "ROC-AUC", "Model comparison", "Feature selection", "Hyperparameter concepts", "Error analysis"],
    10: ["K-Means", "Hierarchical clustering", "DBSCAN", "PCA", "t-SNE concepts", "Numerical transformations", "Categorical encoding", "Scaling", "Feature selection", "Derived features", "Segmentation", "Pattern discovery", "Comparing engineered vs raw features"],
    11: ["Neural networks", "Perceptron", "Neurons", "Layers", "Input layer", "Hidden layers", "Output layer", "Activation functions", "Forward propagation", "Backpropagation", "Gradient descent", "TensorFlow", "Keras", "ANN", "ANN classification", "ANN regression", "CNN fundamentals"],
    12: ["What is NLP?", "Text data", "Text preprocessing", "Tokenization", "Stop words", "Stemming", "Lemmatization", "Bag of Words", "TF-IDF", "Word embeddings", "Basic text classification", "Sentiment analysis"],
    13: ["Error analysis", "Model comparison", "Model improvement", "Hyperparameter concepts", "Reproducibility", "Git", "GitHub", "Experiment tracking concepts", "MLflow fundamentals", "Model versioning", "Model monitoring concepts", "Streamlit", "FastAPI concepts", "Docker concepts", "Basic application deployment"],
    14: ["GitHub portfolio", "Project organization", "README creation", "Documentation", "Project presentation", "Resume project descriptions", "Technical interview preparation", "Data Science interview questions", "Explaining models", "Explaining technical decisions", "Mock interview", "Technical presentation", "Viva / technical defense"],
}

CAPSTONE_WORKFLOW = ["Problem Definition", "Data Understanding", "Data Collection", "Data Cleaning", "EDA", "Statistics", "Feature Engineering", "Machine Learning", "Model Evaluation", "Deployment", "Communication"]


def get_data_science_module(module_number: int) -> Optional[Dict[str, Any]]:
    for module in MODULES:
        if module["number"] == module_number:
            result = deepcopy(module)
            result["topic_details"] = deepcopy(TOPIC_DETAILS.get(module_number, []))
            result["project_time"] = "Embedded within the module."
            return result
    return None


def get_all_data_science_modules() -> List[Dict[str, Any]]:
    return [get_data_science_module(m["number"]) for m in MODULES]


def get_data_science_curriculum() -> Dict[str, Any]:
    return {"course_id": DATA_SCIENCE_COURSE_ID, "curriculum_version": DATA_SCIENCE_CURRICULUM_VERSION, "modules": get_all_data_science_modules(), "capstone": {"title": "End-to-End Data Science Project", "workflow": deepcopy(CAPSTONE_WORKFLOW)}}


def validate_curriculum() -> Dict[str, Any]:
    errors = []
    if len(MODULES) != 14: errors.append("Expected 14 modules.")
    total = sum(m["hours"] for m in MODULES)
    if total != 60: errors.append(f"Expected 60 module hours, got {total}.")
    if [m["number"] for m in MODULES] != list(range(1, 15)): errors.append("Module numbering is not 1-14.")
    if any(not TOPIC_DETAILS.get(m["number"]) for m in MODULES): errors.append("One or more modules lack detailed topics.")
    return {"valid": not errors, "errors": errors, "module_count": len(MODULES), "total_hours": total}


def add_curriculum_to_master_kb(kb):
    report = validate_curriculum()
    if not report["valid"]: raise ValueError(report["errors"])
    course = kb.get_course(DATA_SCIENCE_COURSE_ID)
    if course is None: raise KeyError("Data Science course is missing from Master KB.")
    knowledge = deepcopy(course.knowledge)
    knowledge["detailed_curriculum"] = get_data_science_curriculum()
    course.knowledge = knowledge
    kb.register_course(course)
    return kb


def build_master_kb_with_curriculum():
    from Sayyed_EdVantage_Master_KB_BATCH02 import build_master_kb_with_data_science
    return add_curriculum_to_master_kb(build_master_kb_with_data_science())
