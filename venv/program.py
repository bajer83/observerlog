from PyQt5.QtWidgets import *
from PyQt5 import QtWidgets
from digiGUI import Ui_MainWindow
from collections import namedtuple

import serial
import serial.tools.list_ports
import sys
import threading
import time
import re
import os
import socket
import xml.etree.ElementTree as ET


class mywindow(QtWidgets.QMainWindow):

    def __init__(self):
        super(mywindow, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # self.scrollLabel.setText('No data')
        # self.ui.scrollArea.setWidgetResizable(True)
        # self.ui.scrollArea.setWidget(self.scrollLabel)

        self.ui.pushButton.clicked.connect(self.buttonClicked)
        self.ui.pushButtonTCP.clicked.connect(self.create_TCP_server)

        # TODO: Add a check for number of COM ports detected. If none the program will currently crash.ddd
        self.ui.comboBox.addItems(self.read_available_com_ports())  # creating and initilising Combobox

        self.ser = serial.Serial()
        self.ser.baudrate = 9600

        self.ui.tCPServerIPLineEdit.setText(socket.gethostbyname(socket.getfqdn()))
        self.ui.tCPServerPortLineEdit.setText("7777")

        self.stopEvent = threading.Event()  # an object that will act as a flag to stop while loop for reading serial data
        self.stop_event_for_TCP = threading.Event()  # as above just for TCP server button

        #   Signals

        self.ui.menubar.triggered.connect(self.menu_about_clicked)

    def menu_about_clicked(self, q):
        print("Clicked menue About")

    def buttonClicked(self):
        self.connect(self.stopEvent)

    def read_available_com_ports(self):
        # Creates a list with available COM ports using list comprehension
        return [comport.device for comport in serial.tools.list_ports.comports()]

    def connect(self, stop_event):

        if not self.ser.is_open:
            self.ser.port = self.ui.comboBox.itemText(0)
            self.ser.open()
            self.ui.pushButton.setText('Disconnect')

            t1 = threading.Thread(target=self.readSerialData, args=(self.ser, self.stopEvent))
            t1.daemon = True
            t1.start()

        else:
            print('Port was already opened')
            self.stopEvent.set()  # Event object set to false which will tell thread to terminate soon
            self.ser.close()
            self.ui.pushButton.setText('Connect')

    def readSerialData(self, ser, stopEvent):

        while not stopEvent.is_set():
            data = ser.readline().decode('utf-8')
            print(data)
            parsed_depths = self.parse_bird_data(data)
            self.write_to_file(parsed_depths)

            self.updateScrollArea(data)
        self.stopEvent.clear()  # clears the Flag for the Event object

    def parse_bird_data(self, raw_data):
        parsed_information = {}
        single_line_regex = re.compile(r'BT[\d-]{12}', re.DOTALL | re.IGNORECASE)
        raw_birds = single_line_regex.findall(raw_data)

        for bird in raw_birds:
            bird_number = bird[2:4]
            bird_depth = int(bird[4:8]) / 100
            parsed_information[bird_number] = bird_depth

        return parsed_information

    def write_to_file(self, data_to_save):
        if len(data_to_save) > 0:
            with open(os.path.join(os.path.abspath('.'), 'digiBirdsDepthsLog.txt'), 'w') as f:
                f.write(str(list(data_to_save.values())).strip(
                    '[]'))  # convert dictionary values to list and subseqently to string in order to use strip function to remove brackets

    def updateScrollArea(self, text):
        self.ui.scrollLabel.setText(text + str(time.time()))

        # self.ui.scrollArea.show()

    def create_TCP_server(self):

        try:
            serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            host = self.ui.tCPServerIPLineEdit.text()
            port = int(self.ui.tCPServerPortLineEdit.text())

            serversocket.bind((host, port))

            serversocket.listen(5)

            t1 = threading.Thread(target=self.run_server, args=(serversocket,))
            t1.daemon = True
            t1.start()
        except OSError as err:
            self.stop_event_for_TCP.set()  # informs the accepting thread that it should terminate
            serversocket.close()
            print(f" Socket was opened: {err.strerror}. Socket is now closed.")

    def write_TCP_data(self, data):
        if len(data) > 0:
            # with open(os.path.join(os.path.abspath('.'), 'tcpDataLog.txt'), 'w') as f:
            #     f.write(data)

            print(f"Data from the parsed tuple {data}")
            tree = ET.parse('tcpData.xml')
            root = tree.getroot()

            root.find('feather').text = data.feather
            root.find('wind').text = data.wind
            root.find('line_name').text = data.line_name
            root.find('line_direction').text = data.direction
            root.find('depth').text = data.depth

            tree.write('tcpData.xml')

    def clear_all_labels(self):
        default_text = "N/A"
        self.ui.tcpLabel.setText(default_text)
        self.ui.water_depth_Label.setText(default_text)
        self.ui.dir_label.setText(default_text)
        self.ui.line_name_label.setText(default_text)
        self.ui.wind_speed_label.setText(default_text)

    def parse_tcp_data_update_lables(self, data=str):
        # This implementation relies on fact that only 5 data fields should be received from the TCP source (NG) i.e.
        # feather angle, water depth, wind speed, line direction, line name

        Parsed_tcp_data = namedtuple('Parsed_tcp_data', 'feather depth wind direction line_name')
        parsed_tcp_data_1 = Parsed_tcp_data._make(
            data.split(sep=','))  # this unpacks the list with stirngs into the namedTuple

        self.write_TCP_data(parsed_tcp_data_1)

        self.ui.tcpLabel.setText(parsed_tcp_data_1.feather)
        self.ui.wind_speed_label.setText(parsed_tcp_data_1.wind)
        self.ui.water_depth_Label.setText(parsed_tcp_data_1.depth)
        self.ui.line_name_label.setText(parsed_tcp_data_1.line_name)
        self.ui.dir_label.setText(parsed_tcp_data_1.direction)

    def run_server(self, serversocket):
        client_socket, addr = serversocket.accept()  # blocking funtion which awaits data

        while not self.stop_event_for_TCP.is_set():
            print('inside server : {}'.format(serversocket))

            print('Got a connection from {client}'.format(client=str(addr)))
            self.ui.pushButtonTCP.setText("Disconnect")
            msglist = client_socket.recv(512).strip().splitlines()
            msg = msglist[-1]
            # self.write_TCP_data(msg.decode('ascii'))
            # print('received: {}'.format(msg.decode('ascii')))

            self.parse_tcp_data_update_lables(msg.decode('ascii'))  # section when the labels get updated

        self.stop_event_for_TCP.clear()
        self.ui.pushButtonTCP.setText("Connect")
        self.clear_all_labels()


app = QtWidgets.QApplication([])
app.setStyle('Fusion')
application = mywindow()
application.show()
sys.exit(app.exec())
