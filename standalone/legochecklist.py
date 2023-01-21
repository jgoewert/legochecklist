import sys
from PyQt6.QtWidgets import QApplication, QLabel, QWidget, QGridLayout, QPushButton, QSizePolicy, QScrollArea, QVBoxLayout, QSpinBox
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtCore import Qt, QSize
import requests
import json
import os, os.path

#import urllib.request

class Piece:
    stylesheet = """QSpinBox {
  border: 1px solid #ABABAB;
  border-radius: 3px;
}

QSpinBox::down-button  {
  subcontrol-origin: margin;
  subcontrol-position: center left;
  image: url(:/icons/leftArrow.png);
  background-color: #ABABAB;
  left: 1px;
  height: 24px;
  width: 24px;
}

QSpinBox::up-button  {
  subcontrol-origin: margin;
  subcontrol-position: center right;
  image: url(:/icons/rightArrow.png);
  background-color: #ABABAB;
  right: 1px;
  height: 24px;
  width: 24px;
}"""

    widget = None
    def __init__(self, num, color, img, qty, name):
        self.num = num
        self.name = name
        self.color = color
        self.img = img
        self.qty = qty

    def downloadImage(self):
        if (self.img is not None):
            if not os.path.exists("images"):
                os.mkdir("images")
            if not os.path.exists("images/" + os.path.basename(self.img)):
                #file doesn't exist, download it
                r = requests.get(self.img, stream=True)
                if r.status_code == 200:
                    with open("images/" + os.path.basename(self.img), 'wb') as f:
                        f.write(r.content)

    def getPixmap(self):
        self.downloadImage()
        imgicon = QLabel()
        if self.img is not None:
            filepath = os.path.join("images/", str(os.path.basename(self.img)))
            if os.path.exists(filepath):
                image = QPixmap(filepath)
            else:
                image = QPixmap()
        else:
            image = QPixmap()
        imgicon.setPixmap(image)
        imgicon.setMaximumSize(64,64)
        imgicon.setScaledContents(True)
        return imgicon

    def spinboxchanged(self, value_as_int):
        if value_as_int == self.qty:
            self.widget.setStyleSheet("background-color: green;")
        else:
            self.widget.setStyleSheet("background-color: white;")

    def getWidget(self):
        block = QGridLayout()
        block.addWidget(QLabel(self.num + " - " + self.name),0,0,1,2)
        partImage = self.getPixmap()
        partImage.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        block.addWidget(partImage,1,0,3,1)
        quantityLabel = QLabel("Want\n" + str(self.qty))
        quantityLabel.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        block.addWidget(quantityLabel,1,1)
        haveLabel = QLabel("Have")
        haveLabel.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        block.addWidget(haveLabel,2,1)
        spinbox = QSpinBox()
        spinbox.setMaximum(self.qty)
        spinbox.valueChanged.connect(self.spinboxchanged)
        spinbox.setStyleSheet(self.stylesheet)
        spinbox.setMaximumWidth(100)
        spinbox.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        block.addWidget(spinbox,3,1)
        
        self.widget = QWidget()
        self.widget.setStyleSheet("background-color: white;")
        self.widget.setBaseSize(80,200)
        self.widget.setMaximumWidth(200)
        self.widget.setLayout(block)
        return self.widget

def sort_by_name(list):
    return list["part"]["name"]

def sort_by_color(list):
    return list["color"]["id"]

def sort_by_partnum(list):
    return list["part"]["part_num"]


def main():
    REBRICKABLE_API_KEY = "faef0b1264b7f80e277361182e013d07"
    set_id="1682-1"
    sort_algorithm="name"
    

    app = QApplication([])
    window = QWidget()
    window.setWindowTitle("Lego Checklist Generator")
    window.setGeometry(100,100,1280,980)
   
    toplayout = QGridLayout()
    toplayout.addWidget((QPushButton("Uncomplete")), 0,0)
    toplayout.addWidget((QPushButton("Complete")), 0,1)

    scrollarea = QScrollArea()
    scrollwidget = QWidget()
    scrollvbox = QVBoxLayout()

    #set_id = request.GET.get('set_id','1682-1')
    #sort_algorithm = request.GET.get('sort_algorithm','name')

    fp = requests.get('https://rebrickable.com/api/v3/lego/sets/' + set_id + '?key=' + REBRICKABLE_API_KEY)
    decoded = json.loads(fp.text)
    fp.close()

    set_name = decoded["name"]
   
    fp = requests.get('https://rebrickable.com/api/v3/lego/sets/' + set_id + '/parts/?page_size=1000&key=' + REBRICKABLE_API_KEY)
    decoded = json.loads(fp.text)
    fp.close()
    
    match (sort_algorithm):
        case 'name': 
            sortedresults = sorted(decoded["results"], key=sort_by_name)
        case 'color': 
            sortedresults = sorted(decoded["results"], key=sort_by_color)
        case 'partnum': 
            sortedresults = sorted(decoded["results"], key=sort_by_partnum)
    
    set_pieces = []
    for part in sortedresults:
        if (part['is_spare'] is not True):
            piece = Piece(part["part"]["part_num"], part["color"]["name"], part["part"]["part_img_url"], int(part["quantity"]), part["part"]["name"])
            set_pieces.append(piece)

    for part in set_pieces:
        scrollvbox.addWidget(part.getWidget())

    scrollwidget.setLayout(scrollvbox)

    scrollarea.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
    scrollarea.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scrollarea.setWidgetResizable(True)
    scrollarea.setWidget(scrollwidget)

    scrolllayout = QVBoxLayout()
    scrolllayout.addWidget(scrollarea)

    mainlayout = QGridLayout()
    mainlayout.addLayout(toplayout,0,0)
    mainlayout.addLayout(scrolllayout,1,0)
    window.setLayout(mainlayout)


    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()