import os
import sys

from PyQt5.QAxContainer import *
from PyQt5.QtCore import *
from config.errorCode import *
from PyQt5.QtTest import *
from config.kiwoomType import *

####
import pandas as pd



# 8148267511(모의게좌번호)
class Kiwoom(QAxWidget):
    def __init__(self):
        super().__init__()

        print('**Kiwoom 클래스 입니다**')

        self.realType = RealType()                          #FID 번호를 모아놓은 RealType()클래스를 self.realType변수로 객체화

        ############### eventloop 모음 ###############
        self.login_event_loop = QEventLoop()                #로그인 요충 후 끝날때까지 안전하게 기다리게 만드는 변수 & data를 돌려 받았을떄 데이터들이 event_loop에 걸려있고 거기서 꺼내오는것이다.
        self.detail_account_info_event_loop = QEventLoop()
        self.calculator_event_loop = QEventLoop()
        #############################################

        ################## 스크린번호 모음 ##################
        self.screen_my_info = '2000'            #계좌 관련 스크린 번호
        self.screen_calculation_stock = '4000'  #계산용 스크린 번호
        self.screen_real_stock = '5000'         #종목 별 할당할 스크린 번호
        self.screen_meme_stock = '6000'         #종목 별 할당할 주문용 스크린 번호
        self.screen_start_stop_real = '1000'    #장 시작/종료 실시간 스크린 번호
        #############################################

        ################## 변수 모음 ##################
        self.account_num = None
        self.account_stock_dict = {}                    #계좌평가잔고내역요청
        self.not_account_stock_dict = {}                #실시간미체결주문
        self.stock_info = {'종목코드': [], '종목이름': [], '현재가': [], '전날시가': []}                    #장 마감 후 분석중 조건을 통과한 데이터를 담는다
        self.condition_stock = pd.DataFrame(columns=['종목코드', '종목이름', '현재가', '전날시가'], index=[])           #분석 후 조건을 통과한 데이터를 csv파일에 저장하기 위한 데이터프레임
        self.portfolio_stock_dict = {}                      #전날 분석된 종목들을 불러와서 담는다
        self.jango_dict = {}                            #오늘 산 종목을 모아 놓는 잔고
        ##
        self.one_day_ago = None
        #############################################

        ################## 계좌 관련 변수 모음 ##################
        self.use_money = 0
        self.use_money_percent = 0.05
        ######################################################

        ################## 종목 분석용 변수 모음 ##################
        self.calcul_data = []
        #######################################################

        self.get_ocx_instance()         # 응용프로그램 제어하는 역할
        self.event_slots()              # 키움과 연결하기 위한 시그널 / 슬롯 모음
        self.real_events_slots()        # 실시간 수식 관련 슬롯

        self.signal_login_commConnect()         # 로그인 요청 함수 포함
        self.get_account_info()
        self.detail_account_info()  # 예수금 가져오는 것!
        self.detail_account_mystock()  # 계좌평가 잔고 내용 요청!
        self.non_concluded_account()    # 미체결 요청!
        #QTimer.singleShot(5000, self.non_concluded_account)  # 미체결 요청! / QTimer.singleShot --> 서버 과부화를 막기위해 5초 뒤에 not_concluded_account를 실행하라는 뜻

        #self.file_delete()
        #self.calculator_fnc()



        QTest.qWait(5000)                  #read_code를 실행하기 전에 10초 정도 쉬어 이전 코드의 작업들이 완료되도록 기다리는 역할
        self.read_code()                    #분석한 종목 불러오기
        self.screen_number_setting()            #screen 번호를 할당

        QTest.qWait(5000)

        #실시간 수식 관련 함수
        self.dynamicCall("SetRealReg(QString, QString, QString, QString)", self.screen_start_stop_real, '', self.realType.REALTYPE['장시작시간']['장운영구분'], "0")      #setRealReg 함수에 실시간으로 받고자 하는 종목과 어떤 데이터를 실시간으로 받고 싶은지 지정
        #장이 시작이냐 끝이냐 등록하는 부분 / 두번째 QString은 종목 코드 받는 부분, 그러나 장시작끝을 보기 위해선 빈칸으로 두자/ 프로그램동산 59강강
        #마지막 0은 새로운 실시간 요청을 할 때 사용, 1은 실시간으로 받고 싶은 정보를 추가할때 사용

        for code in self.portfolio_stock_dict.keys():                               #self.portfolio_stock_dict.keys()에 종목마다 스크린 번호를 가지고 있다.
            screen_number = self.portfolio_stock_dict[code]['스크린번호']             #딕셔너리에서 스크린 번호 추출
            fids = self.realType.REALTYPE['주식체결']['체결시간']                      #주식체결에 대한 FID를 꺼내온다 
            self.dynamicCall('SetRealReg(QString, QString, QString, QString)', screen_number, code, fids, '1')
            print('실시간 등록 코드: %s, 스크린번호: %s, fids번호 %s' % (code, screen_number, fids))


    def get_ocx_instance(self):
        # 응용프로그램 제어하는 역할
        self.setControl('KHOPENAPI.KHOpenAPICtrl.1')  # kiwoom api registory


    def event_slots(self):
        # login
        self.OnEventConnect.connect(self.login_slot)                #OnEventConnect --> 로그인이 정상적으로 이루어 졌는지 결과값을 받을 함수 지정, 실행이 아니다
        # TrData(예수금)
        self.OnReceiveTrData.connect(self.trdata_slot)              #OnRecieveTrData --> 조회와 실시간 데이터 처리 겨로가를 받을 함수 지정, 실행이 아니다
        #송수신 메세지
        self.OnReceiveMsg.connect(self.msg_slot)

    def real_events_slots(self):
        #실시간 데이터 받아오기
        self.OnReceiveRealData.connect(self.realdata_slot)          #OnRecieveRealData --> 실시간 이벤트 시그널/ 슬롯 모음
        self.OnReceiveChejanData.connect(self.chejan_slot)          #주문을 널으면 받는 곳

    def signal_login_commConnect(self):
        # login 시도
        self.dynamicCall('CommConnect()')  # CommConnect 함수(로그인 요청하는 시그널 함수)를 dynamicCall 함수를 통해 호출한다.
        self.login_event_loop.exec_()       #이벤트 루프 실행

    def login_slot(self, errCode):
        # 로그인 때 사용 되는 slot & 로그인 성공 여부 반환
        print(errors(errCode))  # errCode == 0 이면 성공, error 타입 반환
        self.login_event_loop.exit()


    def get_account_info(self):  # 계좌 정보 불러오기
        account_list = self.dynamicCall('GetLoginInfo(QString)', 'ACCNO')                   #보유 계좌 번호
        account_user_id = self.dynamicCall('GetLoginInfo(QString)', 'USER_ID')              #사용자 ID
        account_user_name = self.dynamicCall('GetLoginInfo(QString)', 'USER_NAME')          #사용자 이름
        account_server_gubun = self.dynamicCall('GetLoginInfo(QString)', 'GetServerGubun')  # 접속서버구분

        self.account_num = account_list.split(';')[0]               #계좌1;계좌2;계좌3 --> [계좌1, 계좌2, 계좌3]...
        print('나의 보유 계좌번호 :%s' % self.account_num, '/ ' 'user_id: %s' % account_user_id,
              '/ ' 'user_name: %s' % account_user_name)  # 8148267511(모의게좌번호)


    def detail_account_info(self):
        # 예수금 가져오는 부분
        print('********************예수금을 요청하는 부분********************')

        # info 요청
        self.dynamicCall('SetInputValue(QString, QString)', '계좌번호', self.account_num)               # setinputvalue 함수에 기본적인 함수들을 저장
        self.dynamicCall('SetInputValue(QString, QString)', '비밀번호', '0000')
        self.dynamicCall('SetInputValue(QString, QString)', '비밀번호입력매체구분', '00')
        self.dynamicCall('SetInputValue(QString, QString)', '조회구분', '2')
        self.dynamicCall('CommRqData(QString, QString, int, QString)', '예수금상세현황요청', 'opw00001', 0, self.screen_my_info)  # screen number: 하나의 그룹을 만들어 준다.
        # CommRqData() 함수로 트레젝션 요청을 한다/ 받는 부분은 def trdata_slot()에서 받는다. & OnRecieveTrData에서 slot 부분을 할당하고 거기로 저장한다.

        self.detail_account_info_event_loop.exec_()


    def detail_account_mystock(self, sPrevNext='0'):
        '''
        :param sPrevNext: sPrevNext == 0이면 싱글데이터를 받아온다 ?
        :return:
        '''
        # 계좌평가잔고내역요청 가져오는 부분
        print('**********************계좌평가잔고내역요청 요청하는 부분**********************')

        self.dynamicCall('SetInputValue(QString, QString)', '계좌번호', self.account_num)
        self.dynamicCall('SetInputValue(QString, QString)', '비밀번호', '0000')
        self.dynamicCall('SetInputValue(QString, QString)', '비밀번호입력매체구분', '00')
        self.dynamicCall('SetInputValue(QString, QString)', '조회구분', '2')
        self.dynamicCall('CommRqData(QString, QString, int, QString)', '계좌평가잔고내역요청', 'opw00018', sPrevNext, self.screen_my_info)            #
        # CommRqData() 함수로 트레젝션 요청을 한다/ 받는 부분은 def trdata_slot()에서 받는다. & OnRecieveTrData에서 slot 부분을 할당하고 거기로 저장한다.

        self.detail_account_info_event_loop.exec_()


    def non_concluded_account(self, sPrevNext='0'):
        # 실시간미체결주분 가져오는 부분
        print('**********************실시간미체결주문 요청하는 부분**********************')

        self.dynamicCall('SetInputValue(QString, QString)', '계좌번호', self.account_num)
        self.dynamicCall('SetInputValue(QString, QString)', '체결구분', '1')
        self.dynamicCall('SetInputValue(QString, QString)', '매매구분', '0')
        self.dynamicCall('CommRqData(QString, QString, int, QString)', '실시간미체결요청', 'opt10075', sPrevNext, self.screen_my_info)

        self.detail_account_info_event_loop.exec_()


    def trdata_slot(self, sScrNo, sRQName, sTrCode, sRecordName, sPrevNext):
        '''
        tr요철을 받는 구역이다. 슬롯이다.
        :param sScrNo: 스크린번호
        :param sRQName: 내가 요청했을 떄 지은 이름 ex) '실시간미체결요청'
        :param sTrCode: 요청 id, tr코드 ex) opw00018, opt10075
        :param sRecordName: 사용안함
        :param sPrevNext: 다음 페이지가 있는지, 있으면 2로 반환, 없으면 0혹은 없음으로 반환
        :return:
        '''

        if sRQName == '예수금상세현황요청':
            deposit = self.dynamicCall('GetCommData(QString, QString, Int, QString)', sTrCode, sRQName, 0, '예수금')           #GetCommData()는 OnRecieveTrData()이벤트 내에서 사용되는 조회 함수
            print('예수금 %s' % int(deposit))

            self.use_money = int(deposit) * self.use_money_percent  # (예시)1,000,000 * 0.05 = 50,000
            self.use_money = self.use_money / 4  # (예시)50,000 / 4 = 12,500      --> 결국 한 종목을 살때 12,500원 어치를 산다 & 아직 parameter를 더 고민해봐야한다

            possible_deposit = self.dynamicCall('GetCommData(QString, QString, Int, QString)', sTrCode, sRQName, 0, '출금가능금액')
            print('출금가능금액 %s' % int(possible_deposit))

            possible_order_price = self.dynamicCall('GetCommData(QString, QString, Int, QString)', sTrCode, sRQName, 0, '주문가능금액')
            print('주문가능금액 %s' % int(possible_order_price))

            self.detail_account_info_event_loop.exit()

        elif sRQName == '계좌평가잔고내역요청':

            total_buy_money = self.dynamicCall('GetCommData(QString, QString, Int, QString)', sTrCode, sRQName, 0, '총매입금액')
            res_total_buy_money = int(total_buy_money)
            print('총매입금액 %s' % res_total_buy_money)

            total_predict_loss_rate = self.dynamicCall('GetCommData(QString, QString, Int, QString)', sTrCode, sRQName, 0, '총수익률(%)')  # 여기서 0은 첫번쨰 종목을 뜻함, 만약 1이면 두번쨰 종목...
            res_total_predict_loss_rate = float(total_predict_loss_rate)
            print('총수익률(%s) : %s' % ('%', res_total_predict_loss_rate))

            # 보유 종목이 몇개인지 count해서 반환해준다
            rows = self.dynamicCall('GetRepeatCnt(QString, QString)', sTrCode, sRQName)  # GetRepeactCnt를 쓰면 무조건 계좌평가잔고내역의 멀티데이터를 사용하려고 함 & 20개까지 조회 가능
            count = 0
            for i in range(rows):
                #rows를 돌며 안에 있는 종목의 정보를 self.account_stock_dict에 담는 역할
                code = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '종목번호')
                code = code.strip()[1:]  # 앞에 알파벳을 없에자

                code_nm = self.dynamicCall('GetCommData(QString, QString, int, Qstring)', sTrCode, sRQName, i, '종목명')
                stock_quantity = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '보유수량')
                buy_price = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '매입가')
                learn_rate = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '수익률(%)')
                current_price = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '현재가')
                total_chegual_price = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '매입금액')
                possible_quantity = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '매매가능수량')  # 이 외에 나에게 필요한 다른 데이터도 나중에 불러오자
                total_commission = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '수수료합')

                # 형변환환
                code_nm = code_nm.strip()
                stock_quantity = int(stock_quantity.strip())
                buy_price = int(buy_price.strip())
                learn_rate = float(learn_rate.strip())
                current_price = int(current_price.strip())
                total_chegual_price = int(total_chegual_price.strip())
                possible_quantity = int(possible_quantity.strip())
                total_commission = int(total_commission.strip())

                if code in self.account_stock_dict:
                    pass
                else:
                    self.account_stock_dict[code] = {}

                asd = self.account_stock_dict[code]  # 매번 account_stock_dict의 정보를 가지고 오면 아래 주석 처럼 데이터 낭비이기 때문에 미리 찾아 놓자

                '''
                self.account_stock_dict[code].update({'종목명': code_nm})
                self.account_stock_dict[code].update({'보유수량': stock_quantity})
                self.account_stock_dict[code].update({'매입가': buy_price})
                self.account_stock_dict[code].update({'수익률(%)': learn_rate})
                self.account_stock_dict[code].update({'현재가': current_price})
                self.account_stock_dict[code].update({'매입금액': total_chegual_price})
                self.account_stock_dict[code].update({'매매가능수량': possible_quantity})
                '''
                asd.update({'종목명': code_nm})
                asd.update({'보유수량': stock_quantity})
                asd.update({'매입가': buy_price})
                asd.update({'수익률(%)': learn_rate})
                asd.update({'현재가': current_price})
                asd.update({'매입금액': total_chegual_price})
                asd.update({'매매가능수량': possible_quantity})
                asd.update({'수수료합': total_commission})

                count += 1

            print('계좌에 가지고 있는 종목 %s' % self.account_stock_dict)
            print('계좌에 보유종목 카운트 %s' % count)

            if sPrevNext == '2':
                self.detail_account_mystock(sPrevNext = '2')  # 다음 페이지를 조회하겠다는 신호
            else:
                self.detail_account_info_event_loop.exit()  # 더이상 조회할게 없으니 연결을 끝내준다

        elif sRQName == '실시간미체결요청':
            rows = self.dynamicCall('GetRepeatCnt(QString, QString)', sTrCode, sRQName)

            for i in range(rows):
                code = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '종목코드')
                code_nm = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '종목명')
                order_no = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '주문번호')
                order_status = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '주문상태')  # 접수, 확인, 체결
                order_quantity = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '주문수량')
                order_price = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '주문가격')
                order_gubun = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '주문구분')  # -매도, +매수
                not_quantity = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '미체결수량')
                ok_quantity = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '체결량')

                # 형변환환
                code = code.strip()
                code_nm = code_nm.strip()
                order_no = int(order_no.strip())
                order_status = order_status.strip()
                order_quantity = int(order_quantity.strip())
                order_price = int(order_price.strip())
                order_gubun = order_gubun.strip().lstrip('+').lstrip('-')
                not_quantity = int(not_quantity.strip())
                ok_quantity = int(ok_quantity.strip())

                if order_no in self.not_account_stock_dict:
                    pass
                else:
                    self.not_account_stock_dict[order_no] = {}

                nasd = self.not_account_stock_dict[order_no]  # 매번 not_account_stock_dict의 정보를 가지고 오면 아래 주석 처럼 데이터 낭비이기 때문에 미리 찾아 놓자

                '''
                self.not_account_stock_dict[order_no].update({'종목코드': code})
                self.not_account_stock_dict[order_no].update({'종목명': code_nm})
                self.not_account_stock_dict[order_no].update({'주문번호': order_no})
                self.not_account_stock_dict[order_no].update({'주문상태': order_status})
                self.not_account_stock_dict[order_no].update({'주문수량': order_quantity})
                self.not_account_stock_dict[order_no].update({'주문가격': order_price})
                self.not_account_stock_dict[order_no].update({'주문구분': order_gubun})
                self.not_account_stock_dict[order_no].update({'미체결수량': not_quantity})
                self.not_account_stock_dict[order_no].update({'체결량': ok_quantity})
                '''
                nasd.update({'종목코드': code})
                nasd.update({'종목명': code_nm})
                nasd.update({'주문번호': order_no})
                nasd.update({'주문상태': order_status})
                nasd.update({'주문수량': order_quantity})
                nasd.update({'미체결수량': not_quantity})
                nasd.update({'체결량': ok_quantity})
                nasd.update({'주문가격': order_price})
                nasd.update({'주문구분': order_gubun})


                print('미체결 종목 %s' % self.not_account_stock_dict[order_no])
            print('************************************************************')

            self.detail_account_info_event_loop.exit()


        elif sRQName == '주식일봉차트조회':              #오래걸리므로 수정필요

            code = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, 0, '종목코드')
            #code = self.dynamicCall('GetCommDataEx(QString, QString)', sTrCode, sRQName)                       #함수 한번 조회로 600일 치의 데이터를 이중 리스트로 반환
            code = code.strip()
            print('%s 일봉데이터 요청' % code)

            days = self.dynamicCall('GetRepeatCnt(QString, QString)', sTrCode, sRQName)
            print('데이터 일수 %s' % days)
            #한번 조회하면 600일치까지 일봉데이터를 받을 수 있다다
            #data = self.dynamicCall('GetCommDataEx(QString, QString)', sTrCode, sRQName)
            #[['', '현재가', '거래량', '거래대금', '날짜', '시가', '고가', '저가']

            for i in range(days):
                data = []

                current_price = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '현재가')
                value = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '거래량')
                trading_value = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '거래대금')
                date = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '일자')
                start_price = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '시가')
                high_price = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '고가')
                low_price = self.dynamicCall('GetCommData(QString, QString, int, QString)', sTrCode, sRQName, i, '저가')

                data.append('')
                data.append(current_price.strip())
                data.append(value.strip())
                data.append(trading_value.strip())
                data.append(date.strip())
                data.append(start_price.strip())
                data.append(high_price.strip())
                data.append(low_price.strip())
                data.append('')

                self.calcul_data.append(data.copy())            #for문을 돌린 data를 전역 변수에 저장하는 용도



            #if sPrevNext == '2':                                #600일치 이상을 보고 싶으면 sPrevNext를 = '2'로 바꿔서 보자

                #self.day_kiwoom_db(code = code, sPrevNext = sPrevNext)
            nothing = 0                                     #임시
            if nothing == 1:                                #임시
                pass                                        #임시
            else:
                #분석이 끝난후 조건에 부합하는 주식 종목을 뽑고 저장한 후, 다음날 주식 거래에 사용한다

                print('총 일수 %s' % len(self.calcul_data))

                pass_success = False

                #120일 이평선을 그릴만큼의 데이터가 있는지 체크
                if self.calcul_data == None or len(self.calcul_data) < 120:
                    pass_success = False
                else:
                    #120일 이상 되면은

                    #####################################################################
                    #3일 연속 시가가 전 날 시가보다 +면 등록
                    for idx in self.calcul_data[:4]:
                        if idx == self.calcul_data[3]:
                            three_days_ago = int(idx[5])       #idx[5] --> 시가
                        elif idx == self.calcul_data[2]:
                            two_days_ago = int(idx[5])
                        elif idx == self.calcul_data[1]:
                            one_day_ago = int(idx[5])

                    print('3일전 시가: %s' % three_days_ago)
                    print('2일전 시가: %s' % two_days_ago)
                    print('1일전 시가: %s' % one_day_ago)


                    if three_days_ago < two_days_ago and two_days_ago < one_day_ago and one_day_ago < int(self.calcul_data[0][5]):
                        if int(self.calcul_data[0][1]) < 12500:
                            pass_success = True

                    #####################################################################

                    '''
                    total_price = 0
                    for value in self.calcul_data[:120]:
                        total_price += int(value[1])                        #value[1] --> 현재가

                    moving_average_price = total_price / 120                #120일 이평선 오늘치 종가

                    #오늘 주가가 120일 이평선에 걸쳐있는지 확인
                    bottom_stock_price = False
                    check_price = None
                    if int(self.calcul_data[0][7]) <= moving_average_price and moving_average_price <= int(self.calcul_data[0][6]):         #self.calcul_data[0][7] --> 저가, self.calcul_data[0][6] --> 고가
                        print('오늘 주가 120이평선에 걸쳐있는거 확인')
                        bottom_stock_price = True
                        check_price = int(self.calcul_data[0][6])

                    #과거 일봉들이 120일 이평선보다 밑에 있는지 확인, 그리고 그렇게 확인을 하다가 일봉이 120일 이평선보다 위에 있으면 계산 진행
                    prev_price = None                               #과거의 일봉 저가
                    if bottom_stock_price == True:

                        moving_average_price_prev = 0            #해당 일수 부터 다시 120일 이평선을 계산하기 위하여 0으로 다시 setting (과거 데이터)
                        price_top_moving = False

                        idx = 1
                        while True:
                            if len(self.calcul_data[idx:]) < 120: #120일치가 있는지 계속 확인
                                print('120일치가 없음!')
                                break

                            total_price = 0
                            for value in self.calcul_data[idx:120+idx]:
                                total_price += int(value[1])

                            moving_average_price_prev = total_price / 120

                            if moving_average_price_prev <= int(self.calcul_data[idx][6]) and idx <= 20:                        #idx <= 20은 20일치 동안은 일봉이 이평선 아래에 있는 종목들을 고르자는 의미
                                print('20일 동안 주가가 120일 이평선과 같거나 위에 있음')
                                price_top_moving = False
                                break

                            elif int(self.calcul_data[idx][7]) < moving_average_price_prev and idx > 20:
                                print('120일 이평선 위에 있는 일봉 확인됨')
                                prev_price = int(self.calcul_data[idx][7])
                                break

                            idx += 1

                        #해당 부분 이평선이 가장 최근 일자의 이평선 가격보다 낮은지 확인
                        if price_top_moving == True:
                            if moving_average_price > moving_average_price_prev and check_price > prev_price:
                                print('포착된 이평선의 가격이 오늘자(최근일자) 이평선 가격보다 낮은 것 확인됨')
                                print('포착된 부분의 일봉 저가가 오늘자 일봉의 고가보다 낮은지 확인됨')
                                pass_success = True
                '''
                if pass_success == True:
                    print('조건부 통과됨')

                    code_nm = self.dynamicCall('GetMasterCodeName(QString)', code)          #종목 코드로 종목 이름 갖고옴

                    self.stock_info['종목코드'].append(code)
                    self.stock_info['종목이름'].append(code_nm)
                    self.stock_info['현재가'].append(str(self.calcul_data[0][1]))
                    self.stock_info['전날시가'].append(str(self.calcul_data[0][5]))

                elif pass_success == False:
                    print('조건부 통과 못함')


                self.calcul_data.clear()
                self.calculator_event_loop.exit()



    def get_code_list_by_market(self, market_code):
        '''
        주식시장 종목을 가져오는 역할
        종목 코드들 반환 / market_code: 10 = 코스닥
        :param market_code:
        :return:
        '''

        code_list = self.dynamicCall('GetCodeListByMarket(QString)', market_code)   #GetCodeListByMarket --> 주식 시장 종목을 요청하는 함수
        code_list = code_list.split(';')[:-1]
        #https://wikidocs.net/4244 (참고)
        return code_list


    def calculator_fnc(self):
        '''
        종목 분석 실행용 함수
        :return:
        '''
        code_list = self.get_code_list_by_market('10')
        print('코스닥 갯수 %s' % len(code_list))

        for idx, code in enumerate(code_list):              #enumerate을 사용하면 index와 data 둘다 반환한다

            self.dynamicCall('DisconnectRealData(QString)', self.screen_calculation_stock)          #tr요청 전 해당 스크린번호를 끊고 코드를 요청하는 용도
                                                                                                    #스크린번호를 한번이라도 요청하면 그룹이 만들어 진것, 그래서 끊어주는 건 개인의 선택택
            print('%s : %s : KOSDAQ Stock Code: %s is updating... ' % (idx + 1, len(code_list), code))
            self.day_kiwoom_db(code = code)
            if idx == 30:               #임시
                break                   #임시

        self.condition_stock['종목코드'] = self.stock_info['종목코드']
        self.condition_stock['종목이름'] = self.stock_info['종목이름']
        self.condition_stock['현재가'] = self.stock_info['현재가']
        self.condition_stock['전날시가'] = self.stock_info['전날시가']

        self.condition_stock.to_csv('C:/Users/Woo Young Hwang/PycharmProjects/PTP/files/condition_stock.csv', encoding='utf-8-sig')


    def day_kiwoom_db(self, code=None, date=None, sPrevNext='0'):
        # 일봉 데이터 tr요청

        QTest.qWait(3600)   #3.6초 delay를 준다

        self.dynamicCall('SetInputValue(QString, QString)', '종목코드', code)
        self.dynamicCall('SetInputValue(QString, QString)', '수정주가구분', '1')

        if date != None:
            #기준일자를 빈 값으로 요청하면 오늘 날짜부터 조회, 특정 날짜를 기준으로 과거 데이터를 가지고 오고 싶을 때는 YYYYMMDD형식으로 요청
            self.dynamicCall('SetInputValue(QString, QString)', '기준일자', date)

        self.dynamicCall('CommRqData(QString, QString, int, QString)', '주식일봉차트조회', 'opt10081', sPrevNext, self.screen_calculation_stock)  # Tr서버로 전송 -Transaction

        self.calculator_event_loop.exec_()


    def read_code(self):
        #분석한 condition_stock을 불러온다

        if os.path.exists('files/condition_stock.csv'):
            condition_stock = pd.read_csv('C:/Users/Woo Young Hwang/PycharmProjects/PTP/files/condition_stock.csv', dtype = str)
            for line in range(len(condition_stock['종목코드'])):
                if condition_stock.iloc[line][1] != None:
                    stock_code = condition_stock.iloc[line][1]
                    stock_name = condition_stock.iloc[line][2]
                    stock_price = condition_stock.iloc[line][3]
                    yesterday_start_price = condition_stock.iloc[line][4]
                    stock_price = stock_price.strip('-')
                    yesterday_start_price = yesterday_start_price.strip('-')

                    self.portfolio_stock_dict.update({stock_code: {'종목명': stock_name, '현재가': stock_price, '전날시가': yesterday_start_price}})
            print('포토폴리오를 읽습니다....')        #temp
            print(self.portfolio_stock_dict)
            print('***************************************************************')



    def screen_number_setting(self):

        screen_overwrite = []

        #계좌평가잔고내역에 있는 종목들
        for code in self.account_stock_dict.keys():
            if code not in screen_overwrite:
                screen_overwrite.append(code)

        #미체결에 있는 종목들
        for order_number in self.not_account_stock_dict.keys():
            code = self.not_account_stock_dict[order_number]['종목코드']
            if code not in screen_overwrite:
                screen_overwrite.append(code)

        #포트폴리오에 담겨있는 종목들
        for code in self.portfolio_stock_dict.keys():
            if code not in screen_overwrite:
                screen_overwrite.append(code)
        print(screen_overwrite)
        #스크린번호 할당
        count = 0               #스크린번호 하나에 요청 갯수는 100개까지, 스크린 번호는 200개까지 생성가능

        for code in screen_overwrite:

            temp_screen = int(self.screen_real_stock)       #종목 별 할당할 스크린 번호
            meme_screen = int(self.screen_meme_stock)       #종목 별 할당할 주문용 스크린 번호

            if(count % 80) == 0:
                temp_screen += 1                #'5000' --> '5001' 스크린번호 하나당 종목번호 80까지 저장한다는 의미
                self.screen_real_stock = str(temp_screen)

            if (count % 80) == 0:
                meme_screen += 1
                self.screen_meme_stock = str(meme_screen)

            if code in self.portfolio_stock_dict.keys():
                self.portfolio_stock_dict[code].update({'스크린번호': str(self.screen_real_stock)})
                self.portfolio_stock_dict[code].update({'주문용스크린번호': str(self.screen_meme_stock)})
            elif code not in self.portfolio_stock_dict.keys():
                self.portfolio_stock_dict.update({code: {'스크린번호': str(self.screen_real_stock), '주문용스크린번호': str(self.screen_meme_stock)}})

            count += 1
        print('포토폴리오 출력....')       #temp
        print(self.portfolio_stock_dict)
        print('포트폴리오 출력 완료!')       #temp

    def realdata_slot(self, sCode, sRealType, sRealData):
        '''
        실시간 데이터를 받아 오는 부분
        :param sCode:   종목 코드
        :param sRealType:   리얼타입
        :param sRealData:   실시간 데이터 전문 (쓰지 않는다)
        :return:
        '''

        if sRealType == '장시작시간':
            fid = self.realType.REALTYPE[sRealType]['장운영구분']  # (0:장시작전, 2:장종료전(20분), 3:장시작, 4,8:장종료(30분), 9:장마감)
            value = self.dynamicCall("GetCommRealData(QString, int)", sCode, fid)

            if value == '0':
                print('장 시작 전')

            elif value == '3':
                print('장 시작')

            elif value == '2':
                print('장 종료, 동시호가로 넘아감')

            elif value == '4':
                print('3시 30분, 장 종료')

                for code in self.portfolio_stock_dict.keys():
                    self.dynamicCall('SetRealRemove(String, String)', self.portfolio_stock_dict[code]['스크린번호'], code)

                QTest.qWait(5000)
                self.save_account_stock_dict()      #그날의 계좌평가잔고내역을 저장해주자

                self.file_delete()
                self.calculator_fnc()

                sys.exit()

            elif value == '9':
                print('장마감')


        elif sRealType == '주식체결':

            a = self.dynamicCall("GetCommRealData(QString, int)", sCode, self.realType.REALTYPE[sRealType]['체결시간'])      #HHMMSS 형태로 나온다

            b = self.dynamicCall('GetCommRealData(QString, int)', sCode, self.realType.REALTYPE[sRealType]['현재가'])       # +(-) 2500 string 형태
            b = abs(int(b))

            c = self.dynamicCall('GetCommRealData(QString, int)', sCode, self.realType.REALTYPE[sRealType]['전일대비'])      #출력 +(-) 50
            c = abs(int(c))

            d = self.dynamicCall('GetCommRealData(QString, int)', sCode, self.realType.REALTYPE[sRealType]['등락율'])       #출력 +(-) 12.59
            d = float(d)

            e = self.dynamicCall('GetCommRealData(QString, int)', sCode, self.realType.REALTYPE[sRealType]['(최우선)매도호가'])     #매도시가
            e = abs(int(e))

            f = self.dynamicCall('GetCommRealData(QString, int)', sCode, self.realType.REALTYPE[sRealType]['(최우선)매수호가'])     #매수시가
            f = abs(int(f))

            g = self.dynamicCall('GetCommRealData(QString, int)', sCode, self.realType.REALTYPE[sRealType]['거래량'])
            g = abs(int(g))

            h = self.dynamicCall('GetCommRealData(QString, int)', sCode, self.realType.REALTYPE[sRealType]['누적거래량'])
            h = abs(int(h))

            i = self.dynamicCall('GetCommRealData(QString, int)', sCode, self.realType.REALTYPE[sRealType]['고가'])        #오늘자 제일 높은 가격
            i = abs(int(i))

            j = self.dynamicCall('GetCommRealData(QString, int)', sCode, self.realType.REALTYPE[sRealType]['시가'])
            j = abs(int(j))

            k = self.dynamicCall('GetCommRealData(QString, int)', sCode, self.realType.REALTYPE[sRealType]['저가'])        #오늘자 제일 낮은 가격
            k = abs(int(k))

            if sCode not in self.portfolio_stock_dict:
                #만일 종목이 없을 경우를 대비하여, 없으면 포토폴리오에 추가하라는 역할
                self.portfolio_stock_dict.update({sCode: {}})

            self.portfolio_stock_dict[sCode].update({"체결시간": a})
            self.portfolio_stock_dict[sCode].update({"현재가": b})
            self.portfolio_stock_dict[sCode].update({"전일대비": c})
            self.portfolio_stock_dict[sCode].update({"등락율": d})
            self.portfolio_stock_dict[sCode].update({"(최우선)매도호가": e})
            self.portfolio_stock_dict[sCode].update({"(최우선)매수호가": f})
            self.portfolio_stock_dict[sCode].update({"거래량": g})
            self.portfolio_stock_dict[sCode].update({"누적거래량": h})
            self.portfolio_stock_dict[sCode].update({"고가": i})
            self.portfolio_stock_dict[sCode].update({"시가": j})
            self.portfolio_stock_dict[sCode].update({"저가": k})

            print(self.portfolio_stock_dict[sCode])

            #############################################################매도###########################################################

            #계좌잔고평가내역에 있고 오늘 산 잔고에는 없을 경우
            if sCode in self.account_stock_dict.keys() and sCode not in self.jango_dict.keys():       #이전에 사논건지 확인 그리고 오늘 이미 산건지 확인

                asd = self.account_stock_dict[sCode]
                #등락률 (내가 샀던 가격과 현재 시가의 차이)
                meme_rate = (b - asd['매입가']) / asd['매입가'] * 100

                if asd['매매가능수량'] > 0 and (meme_rate > 3 or meme_rate < -3):
                    print('%s %s' % ('신규매도를 한다', sCode))        #temp
                    #주문 signal을 보내자
                    order_success = self.dynamicCall('SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)',
                                     ['신규매도', self.portfolio_stock_dict[sCode]['주문용스크린번호'], self.account_num, 2,                                #주문유형 1:신규매수, 2:신규매도 3:매수취소, 4:매도취소, 5:매수정정, 6:매도정정
                                     sCode, asd['매매가능수량'], 0, self.realType.SENDTYPE['거래구분']['시장가'], ''])

                    if order_success == '0':
                        print('매도주문 전달 성공')
                        del self.account_stock_dict[sCode]      #주문 넣고 해당 딕셔너리 내 delete
                    else:
                        #print(errors(order_success))
                        print('매도주문 전달 실패')



            #오늘 산 잔고에 있을 경우
            elif sCode in self.jango_dict.keys():

                jd = self.jango_dict[sCode]
                meme_rate = (b - jd['매입단가']) / jd['매입단가'] * 100

                if jd['주문가능수량'] > 0 and (meme_rate > 3 or meme_rate < -3):
                    print('%s %s' % ('신규매도를 한다2', sCode))
                    print('오늘 산 잔고에 있을 경우 %s' % meme_rate)  # temp

                    order_success = self.dynamicCall('SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)',
                                                     ['신규매도', self.portfolio_stock_dict[sCode]['주문용스크린번호'], self.account_num, 2, sCode, jd['주문가능수량'], 0, self.realType.SENDTYPE['거래구분']['시장가'],'']
                                                     )

                    if order_success == 0:
                        print('매도 주문 전달 성공')
                    else:

                        print('매도주문 전달 실패')

            #############################################################매수###########################################################

            #전날 시가가 현재 시가보가 낮고 오늘 산 잔고에 없으면 --> 매수
            elif j > int(self.portfolio_stock_dict[sCode].get('전날시가')) and sCode not in self.jango_dict:
                print('%s %s' % ('신규 매수를 한다', sCode))

                result = self.use_money / e  # 현재 내가 가지고 있는 돈에 0.1을 곱하고 현재가로 나누면 몫이 나옴
                quantity = int(result)

                order_success = self.dynamicCall('SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)',
                    ['신규매수', self.portfolio_stock_dict[sCode]['주문용스크린번호'], self.account_num, 1, sCode, quantity, e, self.realType.SENDTYPE['거래구분']['지정가'], ''])

                if order_success == 0:
                    print('매수주문 전달 성공')
                else:
                    print('매수주문 전달 실패')


            '''
            #등락율이 2.0퍼센트 이상이고 오늘 산 잔고에 없으면 (산적이 없는 종목) --> 매수해라
            elif d > 5.0 and sCode not in self.jango_dict:
                print('%s %s' % ('신규 매수를 한다', sCode))

                result = (self.use_money * 0.1) / e     #현재 내가 가지고 있는 돈에 0.1을 곱하고 현재가로 나누면 몫이 나옴
                quantity = int(result)

                order_success = self.dynamicCall('SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)',
                                                     ['신규매수', self.portfolio_stock_dict[sCode]['주문용스크린번호'], self.account_num, 1, sCode, quantity, e, self.realType.SENDTYPE['거래구분']['지정가'], '']
                                                     )
                if order_success == 0:
                    print('매수주문 전달 성공')
                else:
                    print('매수주문 전달 실패')
            '''

            not_meme_list = list(self.not_account_stock_dict)       #데이터 처리 과정에서 업데이트를 방지하기 위해서 list에 넣어 주소를 복사한다. not_account_stock_dict --> 실시간 미체결 리스트
            for order_num in not_meme_list:
                code = self.not_account_stock_dict[order_num]['종목코드']
                meme_price = self.not_account_stock_dict[order_num]['주문가격']
                not_quantity = self.not_account_stock_dict[order_num]['미체결수량']
                #meme_gubun = self.not_account_stock_dict[order_num]['매도수구분']
                order_gubun = self.not_account_stock_dict[order_num]['주문구분']

                #주문을 넣었는데 내가 주문 넣은 가격이 업데이트 되면서 내려가면서 매매가 힘들게 된 경우
                if order_gubun == '매수' and not_quantity > 0 and e > meme_price:
                    print('%s %s' % ('매수최소 한다', sCode))

                    order_success = self.dynamicCall('SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)',
                                                     ['매수취소', self.portfolio_stock_dict[sCode]['주문용스크린번호'], self.account_num, 3, code, 0, 0, self.realType.SENDTYPE['거래구분']['지정가'], order_num]
                                                     )
                    if order_success == 0:
                        print('매수취소 전달 성공')
                    else:
                        print('매수취소 전달 실패')


                #미체결이 0이면 지워주자
                elif not_quantity == 0:
                    del self.not_account_stock_dict[order_num]


    def chejan_slot(self, sGubun, nItemCnt, sFIdList):
        #주문을 넣으면 받는 부분 /sGubun만 쓴다

        if int(sGubun) == '0':      #주문체결
            account_num = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['계좌번호'])
            sCode = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['종목코드'])[1:]
            stock_name = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['종목명'])
            stock_name = stock_name.strip()

            origin_order_number = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['원주문번호'])  # 출력 : defaluse : "000000"
            order_number = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['주문번호'])  # 출럭: 0115061 마지막 주문번호

            order_status = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['주문상태'])  # 출력: 접수, 확인, 체결
            order_quan = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['주문수량'])  # 출력 : 3
            order_quan = int(order_quan)

            order_price = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['주문가격'])  # 출력: 21000
            order_price = int(order_price)

            not_chegual_quan = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['미체결수량'])  # 출력: 15, default: 0
            not_chegual_quan = int(not_chegual_quan)

            order_gubun = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['주문구분'])  # 출력: -매도, +매수
            order_gubun = order_gubun.strip().lstrip('+').lstrip('-')

            chegual_time_str = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['주문/체결시간'])  # 출력: '151028'

            chegual_price = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['체결가'])  # 출력: 2110  default : ''
            if chegual_price == '':
                chegual_price = 0
            else:
                chegual_price = int(chegual_price)

            chegual_quantity = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['체결량'])  # 출력: 5  default : ''
            if chegual_quantity == '':
                chegual_quantity = 0
            else:
                chegual_quantity = int(chegual_quantity)

            current_price = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['현재가'])  # 출력: -6000
            current_price = abs(int(current_price))

            first_sell_price = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['(최우선)매도호가'])  # 출력: -6010
            first_sell_price = abs(int(first_sell_price))

            first_buy_price = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['(최우선)매수호가'])  # 출력: -6000
            first_buy_price = abs(int(first_buy_price))

            #새로 들어간 주문이면 주문번호 할당
            if order_number not in self.not_account_stock_dict.keys():
                self.not_account_stock_dict.update({order_number: {}})

            self.not_account_stock_dict[order_number].update({"종목코드": sCode})
            self.not_account_stock_dict[order_number].update({"주문번호": order_number})
            self.not_account_stock_dict[order_number].update({"종목명": stock_name})
            self.not_account_stock_dict[order_number].update({"주문상태": order_status})
            self.not_account_stock_dict[order_number].update({"주문수량": order_quan})
            self.not_account_stock_dict[order_number].update({"주문가격": order_price})
            self.not_account_stock_dict[order_number].update({"미체결수량": not_chegual_quan})
            self.not_account_stock_dict[order_number].update({"원주문번호": origin_order_number})
            self.not_account_stock_dict[order_number].update({"주문구분": order_gubun})
            self.not_account_stock_dict[order_number].update({"주문/체결시간": chegual_time_str})
            self.not_account_stock_dict[order_number].update({"체결가": chegual_price})
            self.not_account_stock_dict[order_number].update({"체결량": chegual_quantity})
            self.not_account_stock_dict[order_number].update({"현재가": current_price})
            self.not_account_stock_dict[order_number].update({"(최우선)매도호가": first_sell_price})
            self.not_account_stock_dict[order_number].update({"(최우선)매수호가": first_buy_price})

            print('chejan')
            print(self.not_account_stock_dict)


        elif int(sGubun) == '1':

            account_num = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['잔고']['계좌번호'])
            sCode = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['잔고']['종목코드'])[1:]

            stock_name = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['잔고']['종목명'])
            stock_name = stock_name.strip()

            current_price = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['잔고']['현재가'])
            current_price = abs(int(current_price))

            stock_quan = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['잔고']['보유수량'])
            stock_quan = int(stock_quan)

            like_quan = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['잔고']['주문가능수량'])
            like_quan = int(like_quan)

            buy_price = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['잔고']['매입단가'])
            buy_price = abs(int(buy_price))

            total_buy_price = self.dynamicCall("GetChejanData(int)",
                                               self.realType.REALTYPE['잔고']['총매입가'])  # 계좌에 있는 종목의 총매입가
            total_buy_price = int(total_buy_price)

            meme_gubun = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['잔고']['매도매수구분'])
            meme_gubun = self.realType.REALTYPE['매도수구분'][meme_gubun]

            first_sell_price = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['잔고']['(최우선)매도호가'])
            first_sell_price = abs(int(first_sell_price))

            first_buy_price = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['잔고']['(최우선)매수호가'])
            first_buy_price = abs(int(first_buy_price))

            if sCode not in self.jango_dict.keys():
                self.jango_dict.update({sCode: {}})

            self.jango_dict[sCode].update({"현재가": current_price})
            self.jango_dict[sCode].update({"종목코드": sCode})
            self.jango_dict[sCode].update({"종목명": stock_name})
            self.jango_dict[sCode].update({"보유수량": stock_quan})
            self.jango_dict[sCode].update({"주문가능수량": like_quan})
            self.jango_dict[sCode].update({"매입단가": buy_price})
            self.jango_dict[sCode].update({"총매입가": total_buy_price})
            self.jango_dict[sCode].update({"매도매수구분": meme_gubun})
            self.jango_dict[sCode].update({"(최우선)매도호가": first_sell_price})
            self.jango_dict[sCode].update({"(최우선)매수호가": first_buy_price})

            if stock_quan == 0:
                #종목의 보유수량이 0이 되면 없에주자
                del self.jango_dict[sCode]
                self.dynamicCall('SetRealRemove(QString, QString)', self.portfolio_stock_dict[sCode]['스크린번호'], sCode)


    #숭수신 메시지 get (요청 처리가 잘 되고 있는지 보내줌)
    def msg_slot(self, sScrNo, sRQName, sTrCode, msg):
        print('스크린: %s, 요청이름: %s, tr코드: %s --- %s' %(sScrNo, sRQName, sTrCode, msg))

    #파일 삭제
    def file_delete(self):
        if os.path.isfile('files/condition_stock.csv'):
            os.remove('files/condition_stock.csv')

    def save_account_stock_dict(self):
