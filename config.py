"""(3) SINGLETON - one global configuration object."""


class HomeConfig:
    _instance = None                      # - instance: HomeConfig {static}

    def __init__(self):                   # - HomeConfig()  (private by convention)
        if HomeConfig._instance is not None:
            raise RuntimeError("Use HomeConfig.get_instance()")
        self._settings = {"default_driver": "wifi", "home_name": "Goa Villa"}

    @classmethod
    def get_instance(cls) -> "HomeConfig":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get(self, key, default=None):
        return self._settings.get(key, default)

    def set(self, key, value):
        self._settings[key] = value

    @classmethod
    def _reset(cls):                      # only for unit tests
        cls._instance = None
