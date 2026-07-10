"""Dynamic dispatch: the call target isn't known statically."""


def run_named(obj, name):
    """Duck-typed call via getattr -- can't be resolved without running it."""
    method = getattr(obj, name)
    return method()


def call_run():
    """Calls a bare name defined identically in two modules -- ambiguous."""
    return run()
