class ResidualBootstrapNull:
    def fit(self, *args, **kwargs):
        raise NotImplementedError(
            "Residual bootstrap null requires an explicit covariate model and is not part of the default core audit."
        )
