"""Fixture application."""

from util import parse, render_map


class App(Base):
    """Run the app."""

    def start(self):
        return render_map(parse(self.text))


def main(argv):
    """Entry point."""
    app = App()
    return app.start()
