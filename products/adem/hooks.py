"""adem spec-specific surgery (imperative; not expressible as hoist/tag)."""


def preprocess(spec):
    # The spec carries a stray top-level `ExternalTags: {}` key (not a valid OpenAPI
    # root field), which fails OAG spec validation. Drop it.
    spec.pop("ExternalTags", None)
