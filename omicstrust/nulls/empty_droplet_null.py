class EmptyDropletNull:
    def fit(self, *args, **kwargs):
        raise NotImplementedError(
            "Empty-droplet null requires supplied empty-droplet/control observations."
        )
