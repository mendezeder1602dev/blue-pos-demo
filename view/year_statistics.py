from datetime import date

from PyQt5.QtCore import QDate
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QFrame, QToolBar, QHBoxLayout, QLabel, QVBoxLayout, QGridLayout
from PyQt5.uic import loadUi
from pyqtgraph import PlotWidget, PlotItem, AxisItem, ScatterPlotItem, PlotCurveItem, mkPen, mkBrush

from view.util.text_tool_button import ToolButtonWithTextAndIcon
from util.resources_path import resource_path


class YearStatisticsView(QFrame):

    NET_PROFIT_ITEM = 'Ganancias netas'
    SALE_QUANTITY_ITEM = 'Cantidad de ventas'
    TOTAL_EXPENSE_ITEM = 'Gastos totales'

    def __init__(self, presenter):
        super().__init__()
        self.__presenter = presenter
        self.__calculated_year: int = date.today().year

        self.__setup_gui()

    def __setup_gui(self):
        loadUi(resource_path('view/ui/year_statistics.ui'), self)
        self.__setup_tool_bar()
        self.__setup_date_edit()
        self.__setup_combo_box()
        self.__build_summary_panel()
        self.__setup_graph()
        self.__setup_gui_connections()
        self.set_status_bar_message('')

    def __build_summary_panel(self):
        self.summary_header = QFrame()
        self.summary_header.setObjectName('analytics_header')
        summary_layout = QVBoxLayout(self.summary_header)
        summary_layout.setContentsMargins(18, 16, 18, 16)
        summary_layout.setSpacing(10)

        self.period_label = QLabel('Resumen del año')
        self.period_label.setObjectName('analytics_title')
        summary_layout.addWidget(self.period_label)

        self.insight_label = QLabel('Sin datos aún. Calcula el análisis para ver la evolución anual.')
        self.insight_label.setObjectName('analytics_insight')
        self.insight_label.setWordWrap(True)
        summary_layout.addWidget(self.insight_label)

        cards = QGridLayout()
        cards.setHorizontalSpacing(12)
        cards.setVerticalSpacing(12)
        self.kpi_cards = []
        for index, (caption, obj_name) in enumerate([
            ('Ingresos', 'analytics_kpi_sales'),
            ('Utilidad neta', 'analytics_kpi_profit'),
            ('Gastos', 'analytics_kpi_expense'),
            ('Ventas', 'analytics_kpi_count'),
        ]):
            card = QFrame()
            card.setObjectName(obj_name)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 12, 14, 12)
            card_layout.setSpacing(4)
            title = QLabel(caption)
            title.setObjectName('analytics_metric_caption')
            value = QLabel('$ 0.00 MXN')
            value.setObjectName('analytics_metric_value')
            self.kpi_cards.append(value)
            card_layout.addWidget(title)
            card_layout.addWidget(value)
            cards.addWidget(card, index // 2, index % 2)
        summary_layout.addLayout(cards)
        self.main_content_frame.layout().insertWidget(0, self.summary_header)

    def __setup_tool_bar(self):
        self.tool_bar = QToolBar()
        self.tool_bar_frame.setLayout(QHBoxLayout())
        self.tool_bar_frame.layout().setContentsMargins(0, 0, 0, 0)
        self.tool_bar_frame.layout().setMenuBar(self.tool_bar)

        self.back_button = ToolButtonWithTextAndIcon('Atrás')
        self.back_button.set_icon(QPixmap(resource_path('view/ui/images/back.png')))
        self.tool_bar.addWidget(self.back_button)

    def __setup_date_edit(self):
        self.year_date_edit.setMaximumDate(QDate.currentDate())
        self.year_date_edit.setDate(QDate.currentDate())

    def __setup_combo_box(self):
        self.vertical_axes_combo_box.addItems([
            self.NET_PROFIT_ITEM,
            self.SALE_QUANTITY_ITEM,
            self.TOTAL_EXPENSE_ITEM
        ])
        self.vertical_axes_combo_box.setCurrentIndex(0)

    def __setup_graph(self):
        layout = self.graph_frame.layout()
        self.__plot_widget = PlotWidget(parent=self.graph_frame, background='white', foreground='black')
        layout.addWidget(self.__plot_widget)
        self.__set_month_axis_on_plot_item()
        self.__set_axis_limits()
        self.__set_axis_style()
        self.__plot_widget.getPlotItem().getViewBox().setMouseEnabled(x=False, y=False)
        self.__plot_widget.getPlotItem().getViewBox().setMenuEnabled(False)
        self.__plot_widget.getPlotItem().hideButtons()

    def __set_axis_limits(self, min_y: int = 0, max_y: int = 1000):
        self.__plot_widget.getPlotItem().getViewBox().setRange(
            xRange=(1, 12),  # Enero y Diciembre
            yRange=(min_y, max_y)
        )

    def __set_axis_style(self):
        black_pen = mkPen(color='black')

        bottom_axis: AxisItem = self.__plot_widget.getPlotItem().getAxis('bottom')
        bottom_axis.setPen(black_pen)
        bottom_axis.setTextPen(black_pen)

        left_axis: AxisItem = self.__plot_widget.getPlotItem().getAxis('left')
        left_axis.setPen(black_pen)
        left_axis.setTextPen(black_pen)

    def __setup_gui_connections(self):
        self.back_button.clicked.connect(self.__presenter.close_presenter)
        self.calculate_button.clicked.connect(self.__presenter.calculate_economic_month_summaries)
        self.calculate_button.clicked.connect(self.__save_selected_year)
        self.calculate_button.clicked.connect(lambda: self.vertical_axes_combo_box.setDisabled(False))
        self.calculate_button.clicked.connect(lambda: self.__set_graph_title(self.NET_PROFIT_ITEM))
        self.calculate_button.clicked.connect(lambda: self.vertical_axes_combo_box.setCurrentText(self.NET_PROFIT_ITEM))
        self.vertical_axes_combo_box.currentTextChanged.connect(self.__presenter.change_vertical_axis)
        self.vertical_axes_combo_box.currentTextChanged.connect(self.__set_graph_title)

    def __save_selected_year(self):
        self.__calculated_year = self.get_selected_year()

    def __set_graph_title(self, new_text: str):
        self.__plot_widget.getPlotItem()\
            .setTitle(f'<span style="color: #0F172A; font-size: 14px; font-weight: bold;">{new_text} en {self.__calculated_year}</span>')

    def __set_month_axis_on_plot_item(self):
        months_dict = {1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
                       7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre',
                       12: 'Diciembre'}
        month_axis = AxisItem(orientation='bottom',)
        month_axis.setTicks([months_dict.items()])
        plot_item: PlotItem = self.__plot_widget.getPlotItem()
        plot_item.setAxisItems(axisItems={'bottom': month_axis})

    def get_selected_axis(self) -> str:
        return self.vertical_axes_combo_box.currentText()

    def get_selected_year(self) -> int:
        return self.year_date_edit.date().year()

    def disable_gui(self, disable: bool):
        self.main_content_frame.setDisabled(disable)
        self.tool_bar_frame.setDisabled(disable)

    def set_status_bar_message(self, message: str):
        self.status_bar_label.setText(message)

    def set_period_summary(self, period_label: str, insight_text: str, values: dict):
        if hasattr(self, 'period_label'):
            self.period_label.setText(period_label)
        if hasattr(self, 'insight_label'):
            self.insight_label.setText(insight_text)
        if hasattr(self, 'kpi_cards'):
            labels = [
                f"{values.get('sales', 0):,.2f} MXN",
                f"{values.get('net_profit', 0):,.2f} MXN",
                f"-{values.get('expenses', 0):,.2f} MXN",
                str(values.get('operations', 0)),
            ]
            for index, value in enumerate(labels):
                if index < len(self.kpi_cards):
                    self.kpi_cards[index].setText(value)

    def plot_values(self, month_axis: list, y_axis: list):
        self.__plot_widget.getPlotItem().clear()
        if not y_axis:
            return
        self.__draw_graph_lines(month_axis, y_axis)
        self.__draw_graph_points(month_axis, y_axis)
        self.__set_axis_limits(min(y_axis), max(y_axis))

    def __draw_graph_lines(self, month_axis: list, y_axis: list):
        plot_curve_item = PlotCurveItem()
        plot_curve_item.setData(month_axis, y_axis,
                                pen=mkPen({'color': '#0F6FFF', 'width': 2.5}),
                                antialias=True)
        self.__plot_widget.addItem(plot_curve_item)

    def __draw_graph_points(self, month_axis: list, y_axis: list):
        scatter_plot_item = ScatterPlotItem(size=14)
        scatter_plot_item.setData(month_axis, y_axis,
                                  symbol='o',
                                  pen=mkPen({'color': '#0F6FFF'}),
                                  brush=mkBrush('#0F6FFF'),
                                  hoverBrush=mkBrush('#59DBFF'),
                                  hoverable=True,
                                  tip=self.__presenter.create_tool_tip_for_spot,
                                  hoverSize=14)
        self.__plot_widget.addItem(scatter_plot_item)