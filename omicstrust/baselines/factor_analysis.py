def run_factor_analysis_baseline(*args, **kwargs):
    try:
        from sklearn.decomposition import FactorAnalysis
    except Exception as exc:
        raise NotImplementedError("Factor Analysis baseline requires scikit-learn.") from exc
    return FactorAnalysis(*args, **kwargs)
