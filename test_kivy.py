from kivy.app import App  # pyre-ignore
from kivy.uix.label import Label  # pyre-ignore

class TestApp(App):
    def build(self):
        return Label(text="Kivy is Working")

if __name__ == '__main__':
    TestApp().run()
