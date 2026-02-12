import importlib.util
import os

import jinja2
from flask import Flask, render_template, request

from core import ModuleContext

app = Flask(__name__)


def discover_modules():
    """Scan app/modules/ for directories containing module.py and build a registry."""
    modules_dir = os.path.join(os.path.dirname(__file__), "modules")
    registry = []

    if not os.path.isdir(modules_dir):
        return registry

    for name in sorted(os.listdir(modules_dir)):
        mod_file = os.path.join(modules_dir, name, "module.py")
        if os.path.isfile(mod_file):
            spec = importlib.util.spec_from_file_location(f"modules.{name}", mod_file)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            registry.append(
                {
                    "name": name,
                    "title": getattr(mod, "TITLE", name),
                    "description": getattr(mod, "DESCRIPTION", ""),
                    "render": mod.render,
                }
            )

    return registry


# Discover modules and configure Jinja2 template search paths
modules_registry = discover_modules()

app.jinja_loader = jinja2.ChoiceLoader(
    [
        jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__), "templates")),
        jinja2.FileSystemLoader(os.path.dirname(__file__)),
    ]
)


@app.route("/")
def home():
    return render_template("home.html", modules=modules_registry, current_module=None)


def make_module_view(module_entry):
    """Create a view function for a module."""

    def view():
        ctx = ModuleContext(module_entry["name"], request, modules_registry)
        return module_entry["render"](ctx)

    view.__name__ = f"module_{module_entry['name']}"
    return view


for mod in modules_registry:
    app.add_url_rule(f"/{mod['name']}", endpoint=mod["name"], view_func=make_module_view(mod))
