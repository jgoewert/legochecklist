import sys
from PySide6.QtWidgets import QApplication, QLabel, QWidget, QGridLayout, QPushButton, QSizePolicy, QScrollArea, QVBoxLayout, QSpinBox, QLayout
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtCore import Qt, QSize, QRect, QPoint, QMargins
import requests
import json
import os, os.path

#import urllib.request

part_width = 200
set_pieces = []


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
        self.widget.setBaseSize(80,part_width)
        self.widget.setMaximumWidth(part_width)
        self.widget.setMinimumWidth(part_width)
        self.widget.setLayout(block)

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
        return self.widget

def sort_by_name(list):
    return list["part"]["name"]

def sort_by_color(list):
    return list["color"]["id"]

def sort_by_partnum(list):
    return list["part"]["part_num"]

class FlowLayout(QLayout):
    def __init__(self, parent=None):
        super().__init__(parent)

        if parent is not None:
            self.setContentsMargins(QMargins(0, 0, 0, 0))

        self._item_list = []

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self._item_list.append(item)

    def count(self):
        return len(self._item_list)

    def itemAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list[index]

        return None

    def takeAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list.pop(index)

        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        height = self._do_layout(QRect(0, 0, width, 0), True)
        return height

    def setGeometry(self, rect):
        super(FlowLayout, self).setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()

        for item in self._item_list:
            size = size.expandedTo(item.minimumSize())

        size += QSize(2 * self.contentsMargins().top(), 2 * self.contentsMargins().top())
        return size

    def _do_layout(self, rect, test_only):
        x = rect.x()
        y = rect.y()
        line_height = 0
        spacing = self.spacing()

        for item in self._item_list:
            style = item.widget().style()
            layout_spacing_x = style.layoutSpacing(
                QSizePolicy.PushButton, QSizePolicy.PushButton, Qt.Horizontal
            )
            layout_spacing_y = style.layoutSpacing(
                QSizePolicy.PushButton, QSizePolicy.PushButton, Qt.Vertical
            )
            space_x = spacing + layout_spacing_x
            space_y = spacing + layout_spacing_y
            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x = next_x
            line_height = max(line_height, item.sizeHint().height())

        return y + line_height - rect.y()

def main():
    REBRICKABLE_API_KEY = "faef0b1264b7f80e277361182e013d07"
    set_id="1682-1"
    sort_algorithm="name"
    
    app = QApplication([])
    window = QWidget()
    scrollarea = QScrollArea()
    scrollwidget = QWidget()
    scrollvbox = FlowLayout()

    window.setWindowTitle("Lego Checklist Generator")
    window.setGeometry(100,100,1280,980)
    #window.setFixedWidth(1280)
    toplayout = QGridLayout()
    toplayout.addWidget((QPushButton("Uncomplete")), 0,0)
    toplayout.addWidget((QPushButton("Complete")), 0,1)


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