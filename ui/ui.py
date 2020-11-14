from kiwoom.kiwoom import *

import sys
from PyQt5.QtWidgets import *

class Ui_class():
    def __init__(self):
        print('**Ui_class 입니다.**')

        #앱을 실행하기 위해 초기화 해주는 클라스
        self.app = QApplication(sys.argv)

        temp = Kiwoom()
        self.kiwoom = temp


        #app이 실행된 후 종료되는 것을 맏음음
        self.app.exec_()