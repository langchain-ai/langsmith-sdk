"""LangSmith Evaluations.

This module provides a comprehensive suite of tools for evaluating language models and their outputs using LangSmith.

Key Features:
- Robust evaluation framework for assessing model performance across diverse tasks
- Flexible configuration options for customizing evaluation criteria and metrics
- Seamless integration with LangSmith's platform for end-to-end evaluation workflows
- Advanced analytics and reporting capabilities for actionable insights

Usage:
1. Import the necessary components from this module
2. Configure your evaluation parameters and criteria
3. Run your language model through the evaluation pipeline
4. Analyze the results using our built-in tools or export for further processing

Example:
    from langsmith.evaluation import RunEvaluator, MetricCalculator

    evaluator = RunEvaluator(model="gpt-3.5-turbo", dataset_name="customer_support")
    results = evaluator.run()
    metrics = MetricCalculator(results).calculate()

    print(metrics.summary())

For detailed API documentation and advanced usage scenarios, visit the [LangSmith docs](https://docs.langchain.com/langsmith/evaluation-concepts).

!!! note

    This module is designed to work seamlessly with the LangSmith platform.
    Ensure you have the necessary credentials and permissions set up before use.
"""
