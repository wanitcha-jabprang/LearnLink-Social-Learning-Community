from importlib import import_module

from django.apps import AppConfig


class LayeredFeatureConfig(AppConfig):
    model_module = "infrastructure.persistence.models"

    def import_models(self):
        self.models = self.apps.all_models[self.label]
        module_name = f"{self.name}.{self.model_module}"
        self.models_module = import_module(module_name)
