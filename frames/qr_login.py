from PyQt6.QtWidgets import QWidget


class QRLogin(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("QR Login")
        self.show()