from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHBoxLayout, QMessageBox, QSpinBox, QHeaderView, QFileDialog, QComboBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon
import glob
import os
import re
import tkinter as tk
from tkinter import filedialog

import chardet

def smart_open(file_path, mode="r"):
    """
    自动判断编码打开文件，默认文本模式，返回文件对象。
    只能用于读取文本文件。
    """
    if "b" in mode or "w" in mode or "a" in mode:
        # 写入、追加、二进制模式，不动编码，直接返回标准open
        return open(file_path, mode, encoding="utf-8") if "b" not in mode else open(file_path, mode)

    with open(file_path, "rb") as f:
        raw_data = f.read(2048)
    result = chardet.detect(raw_data)
    encoding = result["encoding"] if result["encoding"] else "utf-8"

    return open(file_path, mode, encoding=encoding)

charaparts = []
file_name = ""
charaname = file_name[:-4]       
hasActive= False  
toggleWrite = False
activeWritten = False
skip = -1
existing_conditions=[]
existing_variables=[]
existing_defaults=[]
existing_keys=[]
existing_values=[]
existing_combo_values=[]
existing_endifs=[]
filepath=""
lines=""

class ReorderOnlyTableWidget(QTableWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setDragDropMode(QTableWidget.DragDropMode.NoDragDrop)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        self.setDragDropOverwriteMode(True)
        self.setDropIndicatorShown(False)
        self.viewport().setAcceptDrops(False)
        self.setDefaultDropAction(Qt.DropAction.IgnoreAction)

    def dropEvent(self, event):
        self.blockSignals(True)
        source_row = self.currentRow()
        drop_row = self.rowAt(event.position().toPoint().y())
        if drop_row == -1:
            drop_row = self.rowCount() - 1
        if source_row == drop_row or source_row < 0:
            return

        # 安全克隆源行数据
        items = []
        for c in range(self.columnCount()):
            item = self.item(source_row, c)
            if item is not None:
                items.append(item.clone())
            else:
                items.append(QTableWidgetItem(""))

        # 记住小部件（如组合框和复选框）
        combo_value = None
        checkbox_state = None
        if self.cellWidget(source_row, 4):
            combo_value = self.cellWidget(source_row, 4).currentText()
        if self.item(source_row, 5):
            checkbox_state = self.item(source_row, 5).checkState()

        self.removeRow(source_row)
        if drop_row > source_row:
            drop_row -= 1
        self.insertRow(drop_row)

        for c in range(self.columnCount()):
            if c == 4 and combo_value is not None:
                new_combo = QComboBox()
                new_combo.addItems(["if", "else", "else if", "endif"])
                new_combo.setCurrentText(combo_value)
                self.setCellWidget(drop_row, 4, new_combo)
            elif c == 5 and checkbox_state is not None:
                checkbox_item = QTableWidgetItem()
                checkbox_item.setFlags(checkbox_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                checkbox_item.setCheckState(checkbox_state)
                self.setItem(drop_row, 5, checkbox_item)
            else:
                self.setItem(drop_row, c, items[c])
        event.accept()
        self.blockSignals(False)


class CharacterPartsEditor(QWidget):
    def __init__(self, charaparts, existing_conditions, existing_variables, existing_defaults):
        super().__init__()
        self.charaparts = charaparts
        self.existing_conditions = existing_conditions
        self.existing_variables = existing_variables
        self.existing_defaults = existing_defaults
        self.setMinimumWidth(1000)
        self.setMinimumHeight(700)
        self.setWindowTitle("组件切换工具")
        self.expertMode = False
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.table1 = QTableWidget(0, 6)
        self.table2 = ReorderOnlyTableWidget(len(self.charaparts), 6)
        self.setWindowIcon(QIcon('1-24c533cf.ico'))
        
        self.table1.setHorizontalHeaderLabels(["名称", "INI名称", "快捷键", "默认值", "可选值", "测试值"])
        top_layout = QHBoxLayout()
        top_layout.addStretch()  # 将按钮推到右侧
        open_btn = QPushButton("打开INI")
        open_btn.clicked.connect(self.open_ini_file)
        top_layout.addWidget(open_btn)
        save_btn = QPushButton("保存模板")
        save_btn.clicked.connect(self.save_template)
        top_layout.addWidget(save_btn)
        load_btn = QPushButton("加载模板")
        load_btn.clicked.connect(self.load_template)
        top_layout.addWidget(load_btn)
        help_btn = QPushButton("?")
        help_btn.setFixedSize(30, 30)
        help_btn.clicked.connect(self.show_help)
        top_layout.addWidget(help_btn)
        layout.addLayout(top_layout)
        layout.addWidget(self.table1)

        # 添加一个默认行
        if len(self.existing_variables)==0:
            self.add_row_table1("示例")
        for i, variable_name in enumerate(self.existing_variables):
            self.table1.insertRow(i)
#            print(variable_name)
            name_item = QTableWidgetItem(variable_name)

#            flags = name_item.flags()
#            flags = (flags | Qt.ItemFlag.ItemIsUserCheckable)
#            name_item.setFlags(flags) # enable checkbox
#            name_item.setCheckState(Qt.CheckState.Unchecked)
            self.table1.setItem(i, 0, name_item)
            self.table1.setItem(i, 1, QTableWidgetItem("$"+variable_name))
            self.table1.setItem(i, 2, QTableWidgetItem(existing_keys[i]))
            self.table1.setItem(i, 3, QTableWidgetItem(existing_defaults[i]))
            self.table1.setItem(i, 4, QTableWidgetItem(existing_values[i]))

            
            spin = QSpinBox()
            spin.setMinimum(0)
            spin.setMaximum(999)  # 或任意最大值
            spin.setValue(0)
            spin.valueChanged.connect(lambda value, row=i: self.on_spinbox_changed(row, value))
            self.table1.setCellWidget(i, 5, spin)  # 将微调框放在第5列

        self.set_readOnly(self.table1, 1)  # 使第1列只读

        # 表格1的按钮
        btn_layout1 = QHBoxLayout()
        add_btn1 = QPushButton("添加行")
        remove_btn1 = QPushButton("删除选中行")
        add_btn1.clicked.connect(self.add_row_table1)
        remove_btn1.clicked.connect(self.remove_row_table1)
        btn_layout1.addWidget(add_btn1)
        btn_layout1.addWidget(remove_btn1)
        layout.addLayout(btn_layout1)

        self.table1.itemChanged.connect(self.on_table1_item_changed)

        # 表格2
        self.table2.setHorizontalHeaderLabels(["网格名称", "INI名称", "可见性条件", "可见", "条件类型", "包含endif"])
        self.table2.setColumnHidden(4, True)
        self.table2.setColumnHidden(5, True)
        self.table2.setColumnWidth(2, 500)
        global existing_combo_values
        global existing_endifs

        for i, mesh_name in enumerate(self.charaparts):
            self.table2.setItem(i, 0, QTableWidgetItem(mesh_name))
            ini_name = re.sub(r'[^a-zA-Z0-9\s]', '', mesh_name)
            self.table2.setItem(i, 1, QTableWidgetItem(ini_name))
            self.table2.setItem(i, 2, QTableWidgetItem(existing_conditions[i]))
            combo = QComboBox()
            combo.addItems(["if", "else", "else if", "endif"])
            self.table2.setCellWidget(i, 4, combo)
            checkbox_item = QTableWidgetItem()
            checkbox_item.setFlags(checkbox_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            checkbox_item.setCheckState(Qt.CheckState.Checked)  # 或未选中
            if len(existing_combo_values)==len(charaparts):
                combo = self.table2.cellWidget(i, 4)
                if isinstance(combo, QComboBox):
                    combo.setCurrentText(existing_combo_values[i])
            self.table2.setItem(i, 5, checkbox_item)

            if len(existing_endifs)==len(charaparts):
                if existing_endifs[i]:
                    checkbox_item.setCheckState(Qt.CheckState.Checked)  # 或未选中
                else:
                    checkbox_item.setCheckState(Qt.CheckState.Unchecked)  # 或未选中


        self.table2.resizeColumnToContents(0)
        self.table2.resizeColumnToContents(1)
        self.set_readOnly(self.table2, 0)  # 添加行后重新应用只读
        self.set_readOnly(self.table2, 1)  # 添加行后重新应用只读
        self.set_readOnly(self.table2, 3)  # 添加行后重新应用只读
        layout.addWidget(self.table2)
        self.table2.itemChanged.connect(self.on_table2_item_changed)
        update_btn = QPushButton("更新INI")
        update_btn.clicked.connect(self.update_ini)
        layout.addWidget(update_btn)
        refresh_mesh_btn = QPushButton("刷新网格名称")
        refresh_mesh_btn.clicked.connect(self.refresh_mesh_names)
        layout.addWidget(refresh_mesh_btn)
        self.table1.horizontalHeader().setStretchLastSection(True)
        # 高级模式切换
        self.expert_mode_checkbox = QPushButton("高级模式: 关闭")
        self.expert_mode_checkbox.setCheckable(True)
        self.expert_mode_checkbox.setChecked(False)
        self.expert_mode_checkbox.clicked.connect(self.toggle_expert_mode)
        layout.addWidget(self.expert_mode_checkbox)
        self.table1.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        self.table2.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
    
    def save_template(self):
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "保存模板",
            "",
            "JSON文件 (*.json);;所有文件 (*)"
        )

        if not file_name:
            return  # 用户取消

        # 提取表格1数据
        table1_data = []
        for row in range(self.table1.rowCount()):
            row_data = {
                "名称": self.table1.item(row, 0).text() if self.table1.item(row, 0) else "",
                "INI名称": self.table1.item(row, 1).text() if self.table1.item(row, 1) else "",
                "快捷键": self.table1.item(row, 2).text() if self.table1.item(row, 2) else "",
                "默认值": self.table1.item(row, 3).text() if self.table1.item(row, 3) else "",
                "可选值": self.table1.item(row, 4).text() if self.table1.item(row, 4) else "",
                "测试值": self.table1.cellWidget(row, 5).value() if isinstance(self.table1.cellWidget(row, 5), QSpinBox) else 0
            }
            table1_data.append(row_data)

        # 从表格2提取所有6列
        table2_data = []
        for row in range(self.table2.rowCount()):
            row_data = {
                "网格名称": self.table2.item(row, 0).text() if self.table2.item(row, 0) else "",
                "INI名称": self.table2.item(row, 1).text() if self.table2.item(row, 1) else "",
                "可见性条件": self.table2.item(row, 2).text() if self.table2.item(row, 2) else "",
                "可见": self.table2.item(row, 3).text() if self.table2.item(row, 3) else "",
                "条件类型": "",
                "包含endif": False
            }

            # 第4列（组合框）
            combo = self.table2.cellWidget(row, 4)
            if isinstance(combo, QComboBox):
                row_data["条件类型"] = combo.currentText()

            # 第5列（复选框）
            checkbox_item = self.table2.item(row, 5)
            if checkbox_item is not None:
                row_data["包含endif"] = checkbox_item.checkState() == Qt.CheckState.Checked

            table2_data.append(row_data)

        # 合并为JSON
        template_data = {
            "表格1": table1_data,
            "表格2": table2_data
        }

        # 保存为JSON
        import json
        with open(file_name, "w", encoding="utf-8") as f:
            json.dump(template_data, f, indent=4)

        QMessageBox.information(self, "模板已保存", f"模板已保存至:\n{file_name}")

    
    def load_template(self):
        import json

        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "加载模板",
            "",
            "JSON文件 (*.json);;所有文件 (*)"
        )

        if not file_name:
            return  # 用户取消

        try:
            with smart_open(file_name) as f:
                template_data = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载模板失败:\n{e}")
            return

        # -----------------------------
        # 加载表格1
        # -----------------------------
        self.table1.blockSignals(True)
        self.table2.blockSignals(True)
        self.table1.setRowCount(0)
        for row_data in template_data.get("表格1", []):
            row = self.table1.rowCount()
            self.table1.insertRow(row)
            self.table1.setItem(row, 0, QTableWidgetItem(row_data.get("名称", "")))
            self.table1.setItem(row, 1, QTableWidgetItem(row_data.get("INI名称", "")))
            self.table1.setItem(row, 2, QTableWidgetItem(row_data.get("快捷键", "")))
            self.table1.setItem(row, 3, QTableWidgetItem(row_data.get("默认值", "")))
            self.table1.setItem(row, 4, QTableWidgetItem(row_data.get("可选值", "")))

            spin = QSpinBox()
            spin.setMinimum(0)
            spin.setMaximum(999)
            spin.setValue(row_data.get("测试值", 0))
            spin.valueChanged.connect(lambda value, r=row: self.on_spinbox_changed(r, value))
            self.table1.setCellWidget(row, 5, spin)
        self.set_readOnly(self.table1, 1)
        self.table1.blockSignals(False)

        table2Rows = []
        for i in range(self.table2.rowCount()):
            table2Rows.append(self.table2.item(i, 0).text())

        # -----------------------------
        # 加载表格2
        # -----------------------------
        #self.table2.setRowCount(0)
        row_index=0
        for row_data in template_data.get("表格2", []):
            # row = self.table2.rowCount()

            if row_data.get("网格名称", "") in table2Rows:
                #self.table2.insertRow(row)
                row_index = table2Rows.index(row_data.get("网格名称", ""))
                #print(row_index)
                self.table2.setItem(row_index, 0, QTableWidgetItem(row_data.get("网格名称", "")))
                self.table2.setItem(row_index, 1, QTableWidgetItem(row_data.get("INI名称", "")))
                self.table2.setItem(row_index, 2, QTableWidgetItem(row_data.get("可见性条件", "")))
                self.table2.setItem(row_index, 3, QTableWidgetItem(row_data.get("可见", "")))

                # 第4列: 组合框
                combo = QComboBox()
                combo.addItems(["if", "else", "else if", "endif"])
                combo.setCurrentText(row_data.get("条件类型", "if"))
                self.table2.setCellWidget(row_index, 4, combo)

                # 第5列: 复选框
                checkbox_item = QTableWidgetItem()
                checkbox_item.setFlags(checkbox_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                checkbox_item.setCheckState(Qt.CheckState.Checked if row_data.get("包含endif", False) else Qt.CheckState.Unchecked)
                self.table2.setItem(row_index, 5, checkbox_item)
                row_index+=1

        # 重新设置只读列
        self.set_readOnly(self.table2, 0)
        self.set_readOnly(self.table2, 1)
        self.set_readOnly(self.table2, 3)
        self.table2.blockSignals(False)

        QMessageBox.information(self, "模板已加载", f"模板已从以下位置加载:\n{file_name}")


        
    def toggle_expert_mode(self):
        if self.expert_mode_checkbox.isChecked():
            self.expert_mode_checkbox.setText("高级模式: 开启")
            self.table2.setColumnHidden(4, False)  # 显示"条件类型"列
            self.table2.setColumnHidden(5, False)
            self.expertMode = True
            self.table2.setDragDropMode(QTableWidget.DragDropMode.InternalMove)
            self.table2.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            self.table2.setDragDropOverwriteMode(False)
            self.table2.setDropIndicatorShown(True)
            self.table2.viewport().setAcceptDrops(True)
            self.table2.setDefaultDropAction(Qt.DropAction.MoveAction)
            print("高级模式已启用")
        else:
            self.expert_mode_checkbox.setText("高级模式: 关闭")
            self.table2.setColumnHidden(4, True)  # 隐藏"条件类型"列
            self.table2.setColumnHidden(5, True)
            self.expertMode = False
            self.table2.setDragDropMode(QTableWidget.DragDropMode.NoDragDrop)
            self.table2.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
            self.table2.setDragDropOverwriteMode(True)
            self.table2.setDropIndicatorShown(False)
            self.table2.viewport().setAcceptDrops(False)
            self.table2.setDefaultDropAction(Qt.DropAction.IgnoreAction)
            print("高级模式已禁用")
        
    def show_help(self):
        if not self.expertMode:
            QMessageBox.information(self, "帮助", '''<html><center>
<h2>使用帮助：</h2>
变量的名称和快捷键必须填写！<br><br>
完整的快捷键文档请参考 <a href="https://forums.frontier.co.uk/attachments/edhm-hotkeys-pdf.343006/">这里</a> <br><br>
默认值默认为1。<br><br>
可选值默认为0,1。<br><br>
测试值可用来测试网格可见性以检查错误。<br><br>
点击添加行可添加变量。<br><br>
可见性条件为空表示不会为其生成if语句。<br><br>
<b>刷新网格名称不会丢失变量和条件。</b><br><br>
<br>
条件提示：<br>
<b>变量必须以$开头！</b><br>
&& -> 与<br>
|| -> 或<br>
== -> 等于<br>
!= -> 不等于<br>
可用的数学符号: +,-,/,//,*,%,&lt;,&lt;=,&gt;,&gt;=<br>
</center></html>''')
        else:
            QMessageBox.information(self, "帮助", '''<html><center>
<h2>使用帮助：</h2>
变量的名称和快捷键必须填写！<br><br>
完整的快捷键文档请参考 <a href="https://forums.frontier.co.uk/attachments/edhm-hotkeys-pdf.343006/">这里</a> <br><br>
默认值默认为1。<br><br>
可选值默认为0,1。<br><br>
测试值可用来测试网格可见性以检查错误。<br><br>
点击添加行可添加变量。<br><br>
可见性条件为空表示不会为其生成if语句。<br><br>
<b>刷新网格名称不会丢失变量和条件。</b><br><br>
<br>
条件提示：<br>
<b>变量必须以$开头！</b><br>
&& -> 与<br>
|| -> 或<br>
== -> 等于<br>
!= -> 不等于<br>
可用的数学符号: +,-,/,//,*,%,&lt;,&lt;=,&gt;,&gt;=<br>
<h3>高级模式功能：</h3>
拖动行可以更改网格顺序。<br><br>
有4种条件类型：if, else if, else, 和 endif。<br><br>
<b>if</b>是普通的if语句，带条件。<br>在组件块开头使用此类型。<br><br>
<b>else if</b>是备用的if语句，用作次要条件。<br>不要以此开始组件块<br><br>
<b>else</b>用于所有其他条件。没有条件。<br>仅在组件块中作为最后一个条件使用。<br><br>
<b>endif</b>仅在网格行后写入endif。没有条件。<br>在组件块末尾使用此类型。<br><br>
else和endif在任何情况下都没有条件。<br><br>
在此模式下，每个条件后不会生成endif，<br>
如果要生成endif，请勾选"包含endif"复选框。<br><br>
模板不支持网格重新排序！<br>
</center></html>''')

    def add_row_table1(self, checked=False, default_name=""):
        row_pos = self.table1.rowCount()
        self.table1.insertRow(row_pos)

        name_item = QTableWidgetItem(default_name)
#        flags = name_item.flags()
#        flags = (flags | Qt.ItemFlag.ItemIsUserCheckable)
#        name_item.setFlags(flags) # enable checkbox
#        name_item.setCheckState(Qt.CheckState.Unchecked)
        ini_name = re.sub(r'[^a-zA-Z0-9\s]', '', default_name)
        ini_item = QTableWidgetItem(ini_name.lower())
        self.table1.setItem(row_pos, 0, name_item)
        self.table1.setItem(row_pos, 1, ini_item)
        self.table1.setItem(row_pos, 2, QTableWidgetItem(""))
        self.table1.setItem(row_pos, 3, QTableWidgetItem("1"))
        self.table1.setItem(row_pos, 4, QTableWidgetItem("0,1"))
        spin = QSpinBox()
        spin.setMinimum(0)
        spin.setMaximum(999)  # 或任意最大值
        spin.setValue(0)
        spin.valueChanged.connect(lambda value, row=row_pos: self.on_spinbox_changed(row, value))
        self.table1.setCellWidget(row_pos, 5, spin)  # 将微调框放在第5列
        #active_item = QTableWidgetItem()

        #active_item.setCheckState(Qt.CheckState.Unchecked)  # default unchecked
        #active_item.setText("")
        #self.table1.setItem(row_pos, 4, active_item)  # checkbox column

        self.set_readOnly(self.table1, 1)  # 添加行后重新应用只读
        

    def remove_row_table1(self):
        selected = self.table1.currentRow()
        if selected >= 0:
            self.table1.removeRow(selected)
        else:
            QMessageBox.warning(self, "未选择", "请选择要删除的行。")

    def on_spinbox_changed(self, row, value):
        for i in range(self.table2.rowCount()):
                if self.table2.item(i, 2) is not None:
                    self.on_table2_item_changed(self.table2.item(i, 2))
                else:
                    self.table2.setItem(i, 3, QTableWidgetItem("True"))

    def on_table1_item_changed(self, item):
        if item.column() == 0:
            name = item.text()
            clean_name = re.sub(r'[^a-zA-Z0-9\s]', '', name)
            ini_item = self.table1.item(item.row(), 1)
            if not ini_item:
                ini_item = QTableWidgetItem()
                self.table1.setItem(item.row(), 1, ini_item)
            ini_item.setFlags(ini_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            ini_item.setText("$"+clean_name.lower())
            for i in range(self.table2.rowCount()):
                if self.table2.item(i, 2) is not None:
                    self.on_table2_item_changed(self.table2.item(i, 2))
                else:
                    self.table2.setItem(i, 3, QTableWidgetItem("True"))

    def on_table2_item_changed(self, item):
        condition = item.text()
        self.table2.blockSignals(True)
        variables = re.findall(r'\$[a-zA-Z_][a-zA-Z0-9_]*', condition)
        bad_variables = re.findall(r'(?<!\$)\b[a-zA-Z_][a-zA-Z0-9_]*\b', condition)
        #print(bad_variables)
        vars = []
        item.setBackground(QColor("#2D2D2D"))
        item.setForeground(Qt.GlobalColor.white)      # 白色文本（选中时也可见）
        test_variables= []
        for i in range(self.table1.rowCount()):
            test_variables.append(self.table1.item(i, 1).text().strip())
        for variable in variables:
            if variable.strip() not in test_variables:
                #print("failure!")
                item.setBackground(QColor("red"))
                item.setForeground(QColor("white"))      # 白色文本（选中时也可见）
                self.table2.setItem(item.row(), 3, QTableWidgetItem("错误"))
                self.table2.blockSignals(False)
                return
            
        if len(condition)!=0 and condition!='True':
            
            if self.validate_condition(condition) is not None or len(bad_variables)!=0:
                #print("failure!")
                item.setBackground(QColor("red"))
                item.setForeground(QColor("white"))      # 白色文本（选中时也可见）
                self.table2.setItem(item.row(), 3, QTableWidgetItem("错误"))
                self.table2.blockSignals(False)
                return

            for i in range(self.table1.rowCount()):
                #print(self.table1.item(i, 1).text)
                if(self.table1.item(i, 1).text() in variables):
                    spinbox = self.table1.cellWidget(i, 5)
                    if spinbox and isinstance(spinbox, QSpinBox):
                        val = spinbox.value()
                    #is_checked = self.table1.item(i, 0).checkState() == Qt.CheckState.Checked
                    vars.append((self.table1.item(i, 1).text(), val))
            if len(vars)!=0:
                
                so = self.parse_visibility_condition(condition, dict(vars))  # 输出: True
                if so:
                    self.table2.setItem(item.row(), 3, QTableWidgetItem("True"))
                else:
                    self.table2.setItem(item.row(), 3, QTableWidgetItem("False"))
            else:
                self.table2.setItem(item.row(), 3, QTableWidgetItem("False"))
        else:
            #print("hi")
            self.table2.setItem(item.row(), 3, QTableWidgetItem("True"))
        self.table2.blockSignals(False)

    def validate_condition(self, condition: str) -> str | None:
        # 检测使用 = 而不是 ==
        if re.search(r'(?<![=!<>])=(?![=])', condition):
            return "请使用'=='进行比较而不是'='。"

        # 检测使用 & 或 | 而不是 && 或 ||
        if re.search(r'(?<!&)&(?!&)', condition):
            return "请使用'&&'而不是'&'。"
        if re.search(r'(?<!\|)\|(?!\|)', condition):
            return "请使用'||'而不是'|'。"

        # 检查括号平衡
        if condition.count('(') != condition.count(')'):
            return "检测到未匹配的括号。"

        # 检测两个连续的$变量之间只有空白
        if re.search(r'\$[a-zA-Z_][a-zA-Z0-9_]*\s+\$[a-zA-Z_][a-zA-Z0-9_]*', condition):
            return "两个变量之间缺少运算符。"
        return None  # 无错误


    def set_readOnly(self, table, column):
        for i in range(table.rowCount()):
            item = table.item(i, column)
            if item:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

    def parse_visibility_condition(self, condition, var_values=None):
        if var_values is None:
            var_values = {}

        # 在条件中查找所有$变量
        tokens = re.findall(r'\$[a-zA-Z0-9_]+', condition)

        # 替换为值（如果未提供则默认为1）
        for token in tokens:
            var_name = token
            value = var_values.get(var_name, 1)  # 如果不在字典中则假设为1
            #print(value)
            condition = condition.replace(token, str(value))

        # 将逻辑运算符替换为Python等价物
        condition = condition.replace('&&', 'and').replace('||', 'or')

        try:
            result = eval(condition)
        except Exception as e:
            print(f"评估条件失败: {condition}\n错误: {e}")
            result = False

        return result
    
    def update_ini(self):
        global lines
        global filepath
        print("文件路径: " + filepath)
        match = re.search(r'^.*[\\/]', filepath)
        filename = match.group(0) if match else ''
        print(filename)
        filetoo = match.group(0) if match else ''
        filename = filename+f'DISABLED_BACKUPNOTOGGLE_{charaname}.ini'
        print(filename)
        if os.path.exists(filename):
            msgBox = QMessageBox(self)
            msgBox.setWindowTitle("覆盖文件?")
            msgBox.setText(f"文件'{filename}'已存在。\n是否覆盖?\n警告：此工具基于备份生成ini")
            yesButton = msgBox.addButton("是", QMessageBox.ButtonRole.AcceptRole)
            noButton = msgBox.addButton("否", QMessageBox.ButtonRole.RejectRole)
            msgBox.exec()
            if msgBox.clickedButton() == yesButton:
                with open(filename, "w", encoding="utf-8") as file2:
                    for i, line in enumerate(lines):      
                        file2.write(line)
        else:
            with open(filename, "w", encoding="utf-8") as file2:
                for i, line in enumerate(lines):      
                    file2.write(line)
        print(lines)
        try:
            with smart_open(filename) as file2:
                lines = file2.readlines()
        except FileNotFoundError:
            print(f"错误: 未找到'{filename}'")
        partscounter = 0
        # 创建用于保存的变量
        variables = []
        toggles = []
        defaults = []
        values = []
        for i in range(self.table1.rowCount()):
            variables.append(self.table1.item(i, 0).text())
            if self.table1.item(i, 2) is None or self.table1.item(i, 2).text()=="":
                toggles.append("p")
            else:
                toggles.append(self.table1.item(i, 2).text())
            if self.table1.item(i, 3) is None or self.table1.item(i, 3).text()=="":
                defaults.append("1")
            else:
                defaults.append(self.table1.item(i, 3).text())
            if self.table1.item(i, 4) is None or self.table1.item(i, 4).text()=="":
                values.append("0,1")
            else:
                values.append(self.table1.item(i, 4).text().strip())


        conditions = []
        meshes = []
        for i in range(self.table2.rowCount()):
            meshes.append(self.table2.item(i, 0).text().strip())
            if self.table2.item(i, 2) is None:
                conditions.append("")
            else:
                conditions.append(self.table2.item(i, 2).text().strip())

        check = self.verify_outputs()
        #print(check)
        if check !="":
            self.show_error(check+"\n生成已取消！")
            return

        global toggleWrite
        global skip
        global activeWritten
        activeWritten = False
        with open(filetoo+f'{charaname}.ini', "w", encoding="utf-8") as file:
            print("opening")
            for i, line in enumerate(lines):
                if toggleWrite:
                    if not self.expertMode:
                        condition = conditions[partscounter]
                        if condition != "":
                            file.write("if " + condition.lower().strip() +"\n")
                            #file.write("if $" +charaparts[partscounter].replace(".", "") + "== 1\n")
                            file.write(line)
                            file.write("endif\n")
                        else:
                            file.write(line)
                        partscounter+=1
                        toggleWrite = False
                    else:
                        condition = conditions[partscounter]
                        combo = self.table2.cellWidget(partscounter, 4)
                        if isinstance(combo, QComboBox):
                            value = combo.currentText()
                            endif = self.table2.item(partscounter, 5).checkState() == Qt.CheckState.Checked
                            print("we are here")
                            if value == "if":      
                                if condition != "":
                                    file.write("if " + condition.lower().strip() +"\n")
                                    #file.write("if $" +charaparts[partscounter].replace(".", "") + "== 1\n")
                                    for i in range(len(lines)):
                                        print("looking")
                                        if ("; " + meshes[partscounter] + " (") in lines[i]:
                                            print("Found line:", lines[i])
                                            file.write(lines[i+1])  
                                            break
                                    #file.write(line)
                                    if endif:
                                        file.write("endif\n")
                                else:
                                    for i in range(len(lines)):
                                        print("looking")
                                        if ("; " + meshes[partscounter] + " (") in lines[i]:
                                            print("Found line:", lines[i])
                                            file.write(lines[i+1])  
                                            break  
                            elif value == "else":
                                file.write("else\n")  
                                for i in range(len(lines)):
                                        print("looking")
                                        if ("; " + meshes[partscounter] + " (") in lines[i]:
                                            print("Found line:", lines[i])
                                            file.write(lines[i+1])  
                                            break
                            elif value == "else if":
                                file.write("else if " + condition.lower().strip() +"\n")
                                #file.write("if $" +charaparts[partscounter].replace(".", "") + "== 1\n")
                                for i in range(len(lines)):
                                        print("looking")
                                        if ("; " + meshes[partscounter] + " (") in lines[i]:
                                            print("Found line:", lines[i])
                                            file.write(lines[i+1])  
                                            break
                                if endif:
                                    file.write("endif\n")     
                            else:
                                for i in range(len(lines)):
                                        print("looking")
                                        if ("; " + meshes[partscounter] + " (") in lines[i]:
                                            print("Found line:", lines[i])
                                            file.write(lines[i+1])  
                                            break
                                file.write("endif\n") 
                        partscounter+=1
                        toggleWrite = False
  
                else:
                    if not self.expertMode:
                        if partscounter<len(meshes) and ("; " + meshes[partscounter] + " (") in line:
                            print(line)
                            toggleWrite = True
                        file.write(line)    
                    else:
                        if "; " in line and " (" in line:
                            # split once at "; "
                            after_semicolon = line.split("; ", 1)[1]
                            # split again at " ("
                            mesh_name = after_semicolon.split(" (", 1)[0]
                            if partscounter<len(meshes) and mesh_name in meshes:
                                print(line)
                                toggleWrite = True
                                for look in lines:
                                    print("looking")
                                    if ("; " + meshes[partscounter] + " (") in look:
                                        print("Found line:", look)
                                        file.write(look)  
                                        break
                        else:
                            file.write(line)
                

                if skip>0:
                    skip-=1
                if "; Constants" in line:
                    #print("All the following instructions will ask you to write something.")
                    file.write("[Constants]\n")
                    if hasActive == False:
                        file.write("global $active = 0\n")
                    #if use_settings == False:
                    var=0
                    for i in range(len(variables)):
                        #variable = input("Creating new variable, please write 'skip' to skip\n").strip().lower()
                        variable = variables[var]
                        clean_variable = re.sub(r'[^a-zA-Z0-9\s]', '', variable)
                        file.write("global persist $"+ clean_variable.lower() +" = "+ defaults[var] +"\n")
                        #inputs.append(variable)
                        var+=1



                    file.write("\n[Present]\npost $active = 0\n")
                    for part in range(len(variables)):
                        file.write("\n")
                        clean_part = re.sub(r'[^a-zA-Z0-9\s]', '', variables[part])

                        file.write("[Key"+clean_part+"]\n")
                        #key_input = input("Please enter key to use for the " + part + "\n")
                        file.write("key = " + toggles[part] + "\n")
                        file.write("condition = $active == 1\n")
                        file.write("type = cycle\n")
                        file.write("$"+clean_part.lower()+" = "+values[part]+"\n")
                        #settings_file.write(f"{part}={key_input}\n")
                if hasActive == False:
                    if "TextureOverride" in line and "Texcoord" in line and activeWritten == False:
                        skip = 1
                    if skip == 0:
                        file.write("$active = 1\n")
                        skip=-1
                        activeWritten = True
            return

    def verify_outputs(self):
        for i in range(self.table1.rowCount()):
            if self.table1.item(i, 2) is None or self.table1.item(i,0).text() == "":
                return "变量名称值为空！"
            if self.table1.item(i, 2) is None or self.table1.item(i,2).text() == "":
                return "缺少快捷键！"
            
        for i in range(self.table2.rowCount()):
            if self.table2.item(i, 2) is not None:
                condition = self.table2.item(i, 2).text()
                variables = re.findall(r'\$[a-zA-Z_][a-zA-Z0-9_]*', condition)
                bad_variables = re.findall(r'(?<!\$)\b[a-zA-Z_][a-zA-Z0-9_]*\b', condition)
                test_variables= []
                for i in range(self.table1.rowCount()):
                    test_variables.append(self.table1.item(i, 1).text().strip())
                for variable in variables:
                    if variable.strip() not in test_variables:
                        return "条件中存在错误！"
                    
                    
                if self.validate_condition(condition) is not None or len(bad_variables)!=0:
                    return "条件中存在错误！"
        return ""
    
    def show_error(self, message: str):
        QMessageBox.critical(
            self,
            "错误",
            message,
            QMessageBox.StandardButton.Ok
        )

    def refresh_mesh_names(self):
        global charaparts, existing_conditions
        # 重新提取网格名称
        charaparts.clear()
        print("refreshing")
        conditions=[]
        for i in range(self.table2.rowCount()):
            if self.table2.item(i, 2) is None or self.table2.item(i, 2).text() == "":
                conditions.append([self.table2.item(i, 1).text(), ""])
            else:
                conditions.append([self.table2.item(i, 1).text(), self.table2.item(i, 2).text()])
        #existing_conditions.clear()
        find_file()
        charaparts = extract_charaparts_from_ini()
        #print(charaparts)
        self.table2.blockSignals(True)

        # 清除现有表格2内容
        self.table2.setRowCount(0)
        self.table2.setRowCount(len(charaparts))
        self.table2.setHorizontalHeaderLabels(["网格名称", "INI名称", "可见性条件", "可见"])
        chk = 0
        for i, mesh_name in enumerate(charaparts):
            self.table2.setItem(i, 0, QTableWidgetItem(mesh_name))
            ini_name = re.sub(r'[^a-zA-Z0-9\s]', '', mesh_name)
            self.table2.setItem(i, 1, QTableWidgetItem(ini_name))
            if ini_name == conditions[chk][0]:
                self.table2.setItem(i, 2, QTableWidgetItem(conditions[chk][1]))
                chk+=1
            #if i < len(existing_conditions):
            #    self.table2.setItem(i, 2, QTableWidgetItem(existing_conditions[i]))
            #else:
            #    self.table2.setItem(i, 2, QTableWidgetItem(""))

        self.table2.resizeColumnToContents(0)
        self.table2.resizeColumnToContents(1)
        self.set_readOnly(self.table2, 0)
        self.set_readOnly(self.table2, 1)
        self.set_readOnly(self.table2, 3)
        self.table2.blockSignals(False)

    def open_ini_file(self):
        global file_name, charaname, lines, charaparts, existing_conditions, existing_variables, existing_defaults, existing_keys, existing_values, filepath

        new_file, _ = QFileDialog.getOpenFileName(self, "打开INI文件", "", "INI文件 (*.ini)")
        #file=new_file.name
        if new_file:
            #print(new_file)
            try:
                with smart_open(new_file) as f:
                    filepath=f.name
                    lines = f.readlines()
            except FileNotFoundError:
                QMessageBox.warning(self, "文件错误", "无法读取所选文件。")
                return

            # 更新全局变量
            file_name = new_file
            match = re.search(r'[^\\/]+(?=\.ini$)', file_name, re.IGNORECASE)
            print(charaname)
            charaname = match.group(0) if match else None
            print("2: "+charaname)
            #charaname = os.path.basename(file_name)[:-4]
            existing_variables.clear()
            existing_defaults.clear()
            existing_keys.clear()
            charaparts.clear()
            existing_conditions.clear()
            existing_combo_values.clear()
            existing_endifs.clear()

            # 重新提取所有内容
            extract_charaparts_from_ini()
            #existing_conditions.extend(existing_conditions_tmp)
            #print(existing_conditions)
            # Destroy old UI and rebuild
            self.close()
            self.new_editor = CharacterPartsEditor(charaparts, existing_conditions, existing_variables, existing_defaults)
            self.new_editor.show()




# ------------------------------
# 主入口点
# ------------------------------

def find_file():
    global lines
    global charaname
    global filepath
    file_name = filepath
    match = re.search(r'[^\\/]+(?=\.ini$)', file_name, re.IGNORECASE)

    charaname = match.group(0) if match else None
    if not file_name:
        print("未找到.ini文件。")

    
    try:
        with smart_open(file_name) as file2:
            filepath=file2.name
            #print(file2.name)
            lines = file2.readlines()
    except FileNotFoundError:
        print(f"错误: 未找到'{file_name}'")
def extract_charaparts_from_ini():
    global file_name, charaname, lines, charaparts, existing_conditions, existing_variables, existing_defaults, existing_keys, existing_values, existing_combo_values, existing_endifs
    searching = False

    for i in range(len(lines)):
        if '[' in lines[i] and ']' in lines[i] and searching:
            searching = False
        if 'TextureOverride' in lines[i] and any('ib = ' in lines[i + offset] for offset in range(1, 6) if i + offset < len(lines)):
            searching = True
        if 'global persist' in lines[i]:
            existing_variables.append(re.search(r'\$[a-zA-Z_][a-zA-Z0-9_]*', lines[i]).group()[1:])
            existing_defaults.append(re.search(r'=\s*([0-9]+)', lines[i]).group(1))
        if 'type =' in lines[i-1]:
            existing_values.append(re.search(r'=\s*(.+)', lines[i]).group(1))

        if 'key =' in lines[i]:
            existing_keys.append(re.search(r'=\s*(.+)', lines[i]).group(1))
        if 'drawindexed = ' in lines[i] and 'drawindexed = 0, 0, 0' not in lines[i] and searching:
            if '; ' in lines[i - 1] and "(" in lines[i - 1]:
                if lines[i+1].startswith("endif"):
                    existing_combo_values.append('endif')
                    existing_endifs.append(True)
                else:
                    existing_combo_values.append('if')
                    existing_endifs.append(False)
                charaparts.append(lines[i - 1].split(' (')[0].strip()[2:])
                existing_conditions.append("")
            elif '; ' in lines[i - 2] and "(" in lines[i - 2]:
                
                if lines[i-1].strip().startswith('else if'):
                    existing_combo_values.append('else if')
                elif lines[i-1].strip().startswith('else'):
                    existing_combo_values.append('else')
                else:
                    existing_combo_values.append('if')
                
                if lines[i+1].startswith('endif'):
                    existing_endifs.append(True)
                else:                    
                    existing_endifs.append(False)

                charaparts.append(lines[i - 2].split(' (')[0].strip()[2:])
                existing_conditions.append(re.search(r'\$.*', lines[i - 1]).group())

        if '$active' in lines[i]:
            hasActive = True
    return charaparts

# 运行应用程序
if __name__ == "__main__":
    file_name = next(
        (file for file in glob.glob("*.ini")
         if not file.lower().startswith("disabled") and not file.lower().startswith("backup")),
        None
    )
    filepath=file_name
    #charaname = file_name[:-4]  
    if not file_name:
        root = tk.Tk()
        root.withdraw()  # 隐藏主tkinter窗口
        file_name = filedialog.askopenfilename(
            title="选择INI文件",
            filetypes=[("INI文件", "*.ini")]
        )
        root.destroy()
        if not file_name:  # 用户取消对话框
            print("未选择.ini文件。")
            

    match = re.search(r'[^\\/]+(?=\.ini$)', file_name, re.IGNORECASE)
    charaname = match.group(0) if match else None
    #print(charaname)

    try:
        with smart_open(file_name) as file2:
            filepath=file2.name
            print(file2.name)
            lines = file2.readlines()
    except FileNotFoundError:
        print(f"错误: 未找到'{file_name}'")
    app = QApplication([])
    charaparts = extract_charaparts_from_ini()
    editor = CharacterPartsEditor(charaparts, existing_conditions, existing_variables, existing_defaults)
    editor.show()
    app.exec()
