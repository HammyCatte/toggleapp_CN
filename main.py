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

        # Safely clone source row data
        items = []
        for c in range(self.columnCount()):
            item = self.item(source_row, c)
            if item is not None:
                items.append(item.clone())
            else:
                items.append(QTableWidgetItem(""))

        # Remember widgets (like combo and checkbox)
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
        self.setWindowTitle("Ultimate Component Toggle Tool")
        self.expertMode = False
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.table1 = QTableWidget(0, 6)
        self.table2 = ReorderOnlyTableWidget(len(self.charaparts), 6)
        self.setWindowIcon(QIcon('1-24c533cf.ico'))
        
        self.table1.setHorizontalHeaderLabels(["Name", "Ini Name", "Key", "Default Value", "Values", "Test Values"])
        top_layout = QHBoxLayout()
        top_layout.addStretch()  # pushes the button to the right
        open_btn = QPushButton("Open INI")
        open_btn.clicked.connect(self.open_ini_file)
        top_layout.addWidget(open_btn)
        save_btn = QPushButton("Save INI template")
        save_btn.clicked.connect(self.save_template)
        top_layout.addWidget(save_btn)
        load_btn = QPushButton("Load INI template")
        load_btn.clicked.connect(self.load_template)
        top_layout.addWidget(load_btn)
        help_btn = QPushButton("?")
        help_btn.setFixedSize(30, 30)
        help_btn.clicked.connect(self.show_help)
        top_layout.addWidget(help_btn)
        layout.addLayout(top_layout)
        layout.addWidget(self.table1)

        # Add one default row
        if len(self.existing_variables)==0:
            self.add_row_table1("Example")
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
            spin.setMaximum(999)  # or any max you want
            spin.setValue(0)
            spin.valueChanged.connect(lambda value, row=i: self.on_spinbox_changed(row, value))
            self.table1.setCellWidget(i, 5, spin)  # put spinner in column 0

        self.set_readOnly(self.table1, 1)  # Make column 1 read-only

        # Buttons for Table 1
        btn_layout1 = QHBoxLayout()
        add_btn1 = QPushButton("Add Row")
        remove_btn1 = QPushButton("Remove Selected Row")
        add_btn1.clicked.connect(self.add_row_table1)
        remove_btn1.clicked.connect(self.remove_row_table1)
        btn_layout1.addWidget(add_btn1)
        btn_layout1.addWidget(remove_btn1)
        layout.addLayout(btn_layout1)

        self.table1.itemChanged.connect(self.on_table1_item_changed)

        # Table 2
        self.table2.setHorizontalHeaderLabels(["Mesh Name", "Ini Name", "Visibility Condition", "Visible", "Condition Type", "endif included"])
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
            checkbox_item.setCheckState(Qt.CheckState.Checked)  # or Unchecked
            if len(existing_combo_values)==len(charaparts):
                combo = self.table2.cellWidget(i, 4)
                if isinstance(combo, QComboBox):
                    combo.setCurrentText(existing_combo_values[i])
            self.table2.setItem(i, 5, checkbox_item)

            if len(existing_endifs)==len(charaparts):
                if existing_endifs[i]:
                    checkbox_item.setCheckState(Qt.CheckState.Checked)  # or Unchecked
                else:
                    checkbox_item.setCheckState(Qt.CheckState.Unchecked)  # or Unchecked


        self.table2.resizeColumnToContents(0)
        self.table2.resizeColumnToContents(1)
        self.set_readOnly(self.table2, 0)  # Re-apply readonly after adding a row
        self.set_readOnly(self.table2, 1)  # Re-apply readonly after adding a row
        self.set_readOnly(self.table2, 3)  # Re-apply readonly after adding a row
        layout.addWidget(self.table2)
        self.table2.itemChanged.connect(self.on_table2_item_changed)
        update_btn = QPushButton("Update INI")
        update_btn.clicked.connect(self.update_ini)
        layout.addWidget(update_btn)
        refresh_mesh_btn = QPushButton("Refresh Mesh Names")
        refresh_mesh_btn.clicked.connect(self.refresh_mesh_names)
        layout.addWidget(refresh_mesh_btn)
        self.table1.horizontalHeader().setStretchLastSection(True)
        # Expert Mode Toggle
        self.expert_mode_checkbox = QPushButton("Expert Mode: OFF")
        self.expert_mode_checkbox.setCheckable(True)
        self.expert_mode_checkbox.setChecked(False)
        self.expert_mode_checkbox.clicked.connect(self.toggle_expert_mode)
        layout.addWidget(self.expert_mode_checkbox)
        self.table1.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        self.table2.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
    
    def save_template(self):
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Save Template As",
            "",
            "JSON Files (*.json);;All Files (*)"
        )

        if not file_name:
            return  # User canceled

        # Extract table1 data
        table1_data = []
        for row in range(self.table1.rowCount()):
            row_data = {
                "Name": self.table1.item(row, 0).text() if self.table1.item(row, 0) else "",
                "IniName": self.table1.item(row, 1).text() if self.table1.item(row, 1) else "",
                "Key": self.table1.item(row, 2).text() if self.table1.item(row, 2) else "",
                "DefaultValue": self.table1.item(row, 3).text() if self.table1.item(row, 3) else "",
                "Values": self.table1.item(row, 4).text() if self.table1.item(row, 4) else "",
                "TestValue": self.table1.cellWidget(row, 5).value() if isinstance(self.table1.cellWidget(row, 5), QSpinBox) else 0
            }
            table1_data.append(row_data)

        # Extract all 6 columns from table2
        table2_data = []
        for row in range(self.table2.rowCount()):
            row_data = {
                "MeshName": self.table2.item(row, 0).text() if self.table2.item(row, 0) else "",
                "IniName": self.table2.item(row, 1).text() if self.table2.item(row, 1) else "",
                "VisibilityCondition": self.table2.item(row, 2).text() if self.table2.item(row, 2) else "",
                "Visible": self.table2.item(row, 3).text() if self.table2.item(row, 3) else "",
                "ConditionType": "",
                "EndifIncluded": False
            }

            # Column 4 (ComboBox)
            combo = self.table2.cellWidget(row, 4)
            if isinstance(combo, QComboBox):
                row_data["ConditionType"] = combo.currentText()

            # Column 5 (Checkbox)
            checkbox_item = self.table2.item(row, 5)
            if checkbox_item is not None:
                row_data["EndifIncluded"] = checkbox_item.checkState() == Qt.CheckState.Checked

            table2_data.append(row_data)

        # Combine into JSON
        template_data = {
            "table1": table1_data,
            "table2": table2_data
        }

        # Save to JSON
        import json
        with open(file_name, "w", encoding="utf-8") as f:
            json.dump(template_data, f, indent=4)

        QMessageBox.information(self, "Template Saved", f"Template saved to:\n{file_name}")

    
    def load_template(self):
        import json

        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Load Template",
            "",
            "JSON Files (*.json);;All Files (*)"
        )

        if not file_name:
            return  # User canceled

        try:
            with open(file_name, "r", encoding="utf-8") as f:
                template_data = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load template:\n{e}")
            return

        # -----------------------------
        # Load table1
        # -----------------------------
        self.table1.blockSignals(True)
        self.table2.blockSignals(True)
        self.table1.setRowCount(0)
        for row_data in template_data.get("table1", []):
            row = self.table1.rowCount()
            self.table1.insertRow(row)
            self.table1.setItem(row, 0, QTableWidgetItem(row_data.get("Name", "")))
            self.table1.setItem(row, 1, QTableWidgetItem(row_data.get("IniName", "")))
            self.table1.setItem(row, 2, QTableWidgetItem(row_data.get("Key", "")))
            self.table1.setItem(row, 3, QTableWidgetItem(row_data.get("DefaultValue", "")))
            self.table1.setItem(row, 4, QTableWidgetItem(row_data.get("Values", "")))

            spin = QSpinBox()
            spin.setMinimum(0)
            spin.setMaximum(999)
            spin.setValue(row_data.get("TestValue", 0))
            spin.valueChanged.connect(lambda value, r=row: self.on_spinbox_changed(r, value))
            self.table1.setCellWidget(row, 5, spin)
        self.set_readOnly(self.table1, 1)
        self.table1.blockSignals(False)

        table2Rows = []
        for i in range(self.table2.rowCount()):
            table2Rows.append(self.table2.item(i, 0).text())

        # -----------------------------
        # Load table2
        # -----------------------------
        #self.table2.setRowCount(0)
        row_index=0
        for row_data in template_data.get("table2", []):
            # row = self.table2.rowCount()
            
            if row_data.get("MeshName", "") in table2Rows:
                #self.table2.insertRow(row)
                row_index = table2Rows.index(row_data.get("MeshName", ""))
                #print(row_index)
                self.table2.setItem(row_index, 0, QTableWidgetItem(row_data.get("MeshName", "")))
                self.table2.setItem(row_index, 1, QTableWidgetItem(row_data.get("IniName", "")))
                self.table2.setItem(row_index, 2, QTableWidgetItem(row_data.get("VisibilityCondition", "")))
                self.table2.setItem(row_index, 3, QTableWidgetItem(row_data.get("Visible", "")))

                # Column 4: ComboBox
                combo = QComboBox()
                combo.addItems(["if", "else", "else if", "endif"])
                combo.setCurrentText(row_data.get("ConditionType", "if"))
                self.table2.setCellWidget(row_index, 4, combo)

                # Column 5: Checkbox
                checkbox_item = QTableWidgetItem()
                checkbox_item.setFlags(checkbox_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                checkbox_item.setCheckState(Qt.CheckState.Checked if row_data.get("EndifIncluded", False) else Qt.CheckState.Unchecked)
                self.table2.setItem(row_index, 5, checkbox_item)
                row_index+=1

        # Make readonly columns readonly again
        self.set_readOnly(self.table2, 0)
        self.set_readOnly(self.table2, 1)
        self.set_readOnly(self.table2, 3)
        self.table2.blockSignals(False)

        QMessageBox.information(self, "Template Loaded", f"Template loaded from:\n{file_name}")


        
    def toggle_expert_mode(self):
        if self.expert_mode_checkbox.isChecked():
            self.expert_mode_checkbox.setText("Expert Mode: ON")
            self.table2.setColumnHidden(4, False)  # Show the "Condition Type" column
            self.table2.setColumnHidden(5, False)
            self.expertMode = True
            self.table2.setDragDropMode(QTableWidget.DragDropMode.InternalMove)
            self.table2.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            self.table2.setDragDropOverwriteMode(False)
            self.table2.setDropIndicatorShown(True)
            self.table2.viewport().setAcceptDrops(True)
            self.table2.setDefaultDropAction(Qt.DropAction.MoveAction)
            print("Expert mode enabled")
        else:
            self.expert_mode_checkbox.setText("Expert Mode: OFF")
            self.table2.setColumnHidden(4, True)  # Hide the "Condition Type" column
            self.table2.setColumnHidden(5, True)
            self.expertMode = False
            self.table2.setDragDropMode(QTableWidget.DragDropMode.NoDragDrop)
            self.table2.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
            self.table2.setDragDropOverwriteMode(True)
            self.table2.setDropIndicatorShown(False)
            self.table2.viewport().setAcceptDrops(False)
            self.table2.setDefaultDropAction(Qt.DropAction.IgnoreAction)
            print("Expert mode disabled")
        
    def show_help(self):
        if not self.expertMode:
            QMessageBox.information(self, "Help", '''<html><center>
<h2>Ultimate Component Toggle Helper:</h2>
Values has a default value of 0,1.<br><br>
Default value is 1.<br><br>
Variable name and key must be filled in!<br><br>
Add rows to add variables.<br><br>
A reminder that keys can have modifiers, for example SHIFT p, or NO_ALT d. <br><br>
An empty visibility condition means that no if statement will be generated for it!<br><br>
Use the test values to check for mesh visibility depending on your variable values and for any errors!<br><br>
<b>Refreshing mesh names will not lose your conditions or variables!</b><br><br>
<br>
Condition tips:<br>
<b>Always start variables with $!</b><br>
&& -> and<br>
|| -> or<br>
== -> Equals<br>
!= -> Not equal<br>
All math symbols: +,-,/,//,*,%,&lt;,&lt;=,&gt;,&gt;=<br>
</center></html>''')
        else:
            QMessageBox.information(self, "Help", '''<html><center>
<h2>Ultimate Component Toggle Helper:</h2>
Values has a default value of 0,1.<br><br>
Default value is 1.<br><br>
Variable name and key must be filled in!<br><br>
Add rows to add variables.<br><br>
A reminder that keys can have modifiers, for example SHIFT p, or NO_ALT d. <br><br>
An empty visibility condition means that no if statement will be generated for it!<br><br>
Use the test values to check for mesh visibility depending on your variable values and for any errors!<br><br>
<b>Refreshing mesh names will not lose your conditions or variables!</b><br><br>
<br>
Condition tips:<br>
<b>Always start variables with $!</b><br>
&& -> and<br>
|| -> or<br>
== -> Equals<br>
!= -> Not equal<br>
All math symbols: +,-,/,//,*,%,&lt;,&lt;=,&gt;,&gt;=
<h3>Expert mode controls:</h3>
Drag and drop the rows to change mesh order.<br><br>
There are 4 condition types: if, else if, else, and endif.<br><br>
<b>if</b> is your normal if statement, with conditions. <br>USE THIS AT THE START OF YOUR COMPONENT BLOCKS.<br><br>
<b>else if</b> is your alternative if statement, used as a secondary condition. <br>DO NOT START COMPONENT BLOCKS WITH THIS<br><br>
<b>else</b> is for all other conditions. It has no conditions. <br>ONLY USE THIS AS YOUR LAST CONDITION IN COMPONENT BLOCKS.<br><br>
<b>endif</b> writes only the endif after the mesh line. It has no conditions. <br>USE THIS AT THE END OF YOUR COMPONENT BLOCKS.<br><br>
else and endif do not have conditions in any scenario.<br><br>
endifs are not generated after each condition in this mode,<br>
if you want to generate an endif please select the checkbox in endif included.<br><br>
Templates do not support mesh reordering!<br>
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
        spin.setMaximum(999)  # or any max you want
        spin.setValue(0)
        spin.valueChanged.connect(lambda value, row=row_pos: self.on_spinbox_changed(row, value))
        self.table1.setCellWidget(row_pos, 5, spin)  # put spinner in column 0
        #active_item = QTableWidgetItem()

        #active_item.setCheckState(Qt.CheckState.Unchecked)  # default unchecked
        #active_item.setText("")
        #self.table1.setItem(row_pos, 4, active_item)  # checkbox column

        self.set_readOnly(self.table1, 1)  # Re-apply readonly after adding a row
        

    def remove_row_table1(self):
        selected = self.table1.currentRow()
        if selected >= 0:
            self.table1.removeRow(selected)
        else:
            QMessageBox.warning(self, "No selection", "Please select a row to remove.")

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
        item.setForeground(Qt.GlobalColor.white)      # White text (visible even when selected)
        test_variables= []
        for i in range(self.table1.rowCount()):
            test_variables.append(self.table1.item(i, 1).text().strip())
        for variable in variables:
            if variable.strip() not in test_variables:
                #print("failure!")
                item.setBackground(QColor("red"))
                item.setForeground(QColor("white"))      # White text (visible even when selected)
                self.table2.setItem(item.row(), 3, QTableWidgetItem("Error"))
                self.table2.blockSignals(False)
                return
            
        if len(condition)!=0 and condition!='True':
            
            if self.validate_condition(condition) is not None or len(bad_variables)!=0:
                #print("failure!")
                item.setBackground(QColor("red"))
                item.setForeground(QColor("white"))      # White text (visible even when selected)
                self.table2.setItem(item.row(), 3, QTableWidgetItem("Error"))
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
                
                so = self.parse_visibility_condition(condition, dict(vars))  # Output: True
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
        # Detect single = instead of ==
        if re.search(r'(?<![=!<>])=(?![=])', condition):
            return "Use '==' for comparisons instead of '='."

        # Detect single & or | instead of && or ||
        if re.search(r'(?<!&)&(?!&)', condition):
            return "Use '&&' instead of '&'."
        if re.search(r'(?<!\|)\|(?!\|)', condition):
            return "Use '||' instead of '|'."

        # Check parentheses balance
        if condition.count('(') != condition.count(')'):
            return "Unmatched parentheses detected."

        # Detect two consecutive $variables with only whitespace between them
        if re.search(r'\$[a-zA-Z_][a-zA-Z0-9_]*\s+\$[a-zA-Z_][a-zA-Z0-9_]*', condition):
            return "Missing operator between two variables."
        return None  # no error


    def set_readOnly(self, table, column):
        for i in range(table.rowCount()):
            item = table.item(i, column)
            if item:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

    def parse_visibility_condition(self, condition, var_values=None):
        if var_values is None:
            var_values = {}

        # Find all $variables in the condition
        tokens = re.findall(r'\$[a-zA-Z0-9_]+', condition)

        # Replace them with values (default to 1 if not provided)
        for token in tokens:
            var_name = token
            value = var_values.get(var_name, 1)  # assume 1 if not in dict
            #print(value)
            condition = condition.replace(token, str(value))

        # Replace logical operators with Python equivalents
        condition = condition.replace('&&', 'and').replace('||', 'or')

        try:
            result = eval(condition)
        except Exception as e:
            print(f"Failed to evaluate condition: {condition}\nError: {e}")
            result = False

        return result
    
    def update_ini(self):
        global lines
        global filepath
        print("filepath: " + filepath)
        match = re.search(r'^.*[\\/]', filepath)
        filename = match.group(0) if match else ''
        print(filename)
        filetoo = match.group(0) if match else ''
        filename = filename+f'DISABLED_BACKUPNOTOGGLE_{charaname}.ini'
        print(filename)
        if os.path.exists(filename):
            reply = QMessageBox.question(
            self, "Overwrite File?",
            f"The file '{filename}' already exists.\nDo you want to overwrite it?\nA warning that this application bases itself off the backup when generating",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                with open(filename, "w") as file2:
                    for i, line in enumerate(lines):      
                        file2.write(line)
        else:
            with open(filename, "w") as file2:
                for i, line in enumerate(lines):      
                    file2.write(line)
        print(lines)
        try:
            with open(filename) as file2:
                lines = file2.readlines()
        except FileNotFoundError:
            print(f"Error: '{filename}' not found.")
        partscounter = 0
        # Create variables for saving
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
            self.show_error(check+"\nGeneration cancelled!")
            return

        global toggleWrite
        global skip
        global activeWritten
        activeWritten = False
        with open(filetoo+f'{charaname}.ini', "w") as file:
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
                return "Empty variable name values!"
            if self.table1.item(i, 2) is None or self.table1.item(i,2).text() == "":
                return "Missing toggle keys!"
            
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
                        return "Error in conditions!"
                    
                    
                if self.validate_condition(condition) is not None or len(bad_variables)!=0:
                    return "Error in conditions!"
        return ""
    
    def show_error(self, message: str):
        QMessageBox.critical(
            self,
            "Error",
            message,
            QMessageBox.StandardButton.Ok
        )

    def refresh_mesh_names(self):
        global charaparts, existing_conditions
        # Re-extract mesh names
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

        # Clear existing table2 content
        self.table2.setRowCount(0)
        self.table2.setRowCount(len(charaparts))
        self.table2.setHorizontalHeaderLabels(["Mesh Name", "Ini Name", "Visibility Condition", "Visible"])
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

        new_file, _ = QFileDialog.getOpenFileName(self, "Open INI File", "", "INI Files (*.ini)")
        #file=new_file.name
        if new_file:
            #print(new_file)
            try:
                with open(new_file) as f:
                    filepath=f.name
                    lines = f.readlines()
            except FileNotFoundError:
                QMessageBox.warning(self, "File Error", "Selected file could not be read.")
                return

            # Update globals
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

            # Re-extract everything
            extract_charaparts_from_ini()
            #existing_conditions.extend(existing_conditions_tmp)
            #print(existing_conditions)
            # Destroy old UI and rebuild
            self.close()
            self.new_editor = CharacterPartsEditor(charaparts, existing_conditions, existing_variables, existing_defaults)
            self.new_editor.show()




# ------------------------------
# Main entry point
# ------------------------------

def find_file():
    global lines
    global charaname
    global filepath
    file_name = filepath
    match = re.search(r'[^\\/]+(?=\.ini$)', file_name, re.IGNORECASE)

    charaname = match.group(0) if match else None
    if not file_name:
        print("No .ini file found.")

    
    try:
        with open(file_name) as file2:
            filepath=file2.name
            #print(file2.name)
            lines = file2.readlines()
    except FileNotFoundError:
        print(f"Error: '{file_name}' not found.")
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

# Run the app
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
        root.withdraw()  # Hide the main tkinter window
        file_name = filedialog.askopenfilename(
            title="Select an INI file",
            filetypes=[("INI files", "*.ini")]
        )
        root.destroy()
        if not file_name:  # User cancelled the dialog
            print("No .ini file selected.")
            

    match = re.search(r'[^\\/]+(?=\.ini$)', file_name, re.IGNORECASE)
    charaname = match.group(0) if match else None
    #print(charaname)

    try:
        with open(file_name) as file2:
            filepath=file2.name
            print(file2.name)
            lines = file2.readlines()
    except FileNotFoundError:
        print(f"Error: '{file_name}' not found.")
    app = QApplication([])
    charaparts = extract_charaparts_from_ini()
    editor = CharacterPartsEditor(charaparts, existing_conditions, existing_variables, existing_defaults)
    editor.show()
    app.exec()
