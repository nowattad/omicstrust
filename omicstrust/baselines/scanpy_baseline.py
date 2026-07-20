def run_scanpy_baseline(*args, **kwargs):
    try:
        import scanpy  # noqa: F401
    except Exception as exc:
        raise NotImplementedError("Scanpy baseline is optional and requires scanpy.") from exc
    raise NotImplementedError("Scanpy baseline workflow is intentionally optional and not run by the core audit.")
