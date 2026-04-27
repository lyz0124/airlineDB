import os
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from flaskr import create_app
else:
    from . import create_app

airline = create_app()


if __name__ == "__main__":
    airline.run(debug=True)
