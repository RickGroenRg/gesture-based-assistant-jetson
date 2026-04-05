from jarvis_gesture.app import JarvisGestureApp
from jarvis_gesture.config import AppConfig


if __name__ == "__main__":
    config = AppConfig.from_env()
    app = JarvisGestureApp(config)
    app.run()
