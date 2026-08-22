from datetime import date, timedelta

from PyQt5.QtCore import QDate
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QFrame, QToolBar, QHBoxLayout, QLabel, QVBoxLayout, QGridLayout
from pyqtgraph import PlotWidget, mkPen, AxisItem, PlotCurveItem, ScatterPlotItem, mkBrush
from PyQt5.uic import loadUi

from view.util.text_tool_button import ToolButtonWithTextAndIcon
from util.resources_path import resource_path


class MonthStatisticsView(QFrame):

    NET_PROFIT_ITEM = 'Ganancias netas'
    SALE_QUANTITY_ITEM = 'Cantidad de ventas'
    TOTAL_EXPENSE_ITEM = 'Gastos totales'

    def __init__(self, presenter):
        super().__init__()
        self.__presenter = presenter
        self.__calculated_month_date: date = None

        self.__setup_gui()

    def __setup_gui(self):
        loadUi(resource_path('view/ui/month_statistics.ui'), self)
        self.__setup_back_tool_button()
        self.__setup_date_edit()
        self.__setup_axis_combo_box()
        self.__build_summary_panel()
        self.__setup_graph()
        self.__setup_gui_connections()

    def __build_summary_panel(self):
        self.summary_header = QFrame()
        self.summary_header.setObjectName('analytics_header')
        summary_layout = QVBoxLayout(self.summary_header)
        summary_layout.setContentsMargins(18, 16, 18, 16)
        summary_layout.setSpacing(10)

        self.period_label = QLabel('Resumen del periodo')
        self.period_label.setObjectName('analytics_title')
        summary_layout.addWidget(self.period_label)

        self.insight_label = QLabel('Sin datos aún. Calcula el análisis para visualizar tendencia y rendimiento.')
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
            setattr(self, f'kpi_{index}_label', value)
            self.kpi_cards.append(value)
            card_layout.addWidget(title)
            card_layout.addWidget(value)
            cards.addWidget(card, index // 2, index % 2)
        summary_layout.addLayout(cards)

        self.main_content_frame.layout().insertWidget(0, self.summary_header)

    def __setup_back_tool_button(self):
        self.tool_bar = QToolBar()
        self.tool_bar_frame.setLayout(QHBoxLayout())
        self.tool_bar_frame.layout().setContentsMargins(0, 0, 0, 0)
        self.tool_bar_frame.layout().setMenuBar(self.tool_bar)

        self.back_button = ToolButtonWithTextAndIcon('Atrás')
        self.back_button.set_icon(QPixmap(resource_path('view/ui/images/back.png')))
        self.tool_bar.addWidget(self.back_button)

    def __setup_date_edit(self):
        self.month_date_edit.setMaximumDate(QDate.currentDate())
        self.month_date_edit.setDate(QDate.currentDate())

    def __setup_axis_combo_box(self):
        self.vertical_axes_combo_box.addItems([
            self.NET_PROFIT_ITEM,
            self.SALE_QUANTITY_ITEM,
            self.TOTAL_EXPENSE_ITEM
        ])
        self.vertical_axes_combo_box.setCurrentIndex(0)

    def __setup_graph(self):
        layout = self.graph_frame.layout()
        self.plot_widget = PlotWidget(parent=self.graph_frame, background='white', foreground='black')
        layout.addWidget(self.plot_widget)
        self.__set_axis_style()
        self.plot_widget.getPlotItem().getViewBox().setMouseEnabled(x=False, y=False)
        self.plot_widget.getPlotItem().getViewBox().setMenuEnabled(False)
        self.plot_widget.getPlotItem().hideButtons()

    def __set_axis_style(self):
        black_pen = mkPen(color='black')

        bottom_axis: AxisItem = self.plot_widget.getPlotItem().getAxis('bottom')
        bottom_axis.setPen(black_pen)
        bottom_axis.setTextPen(black_pen)

        left_axis: AxisItem = self.plot_widget.getPlotItem().getAxis('left')
        left_axis.setPen(black_pen)
        left_axis.setTextPen(black_pen)

    def __setup_gui_connections(self):
        self.back_button.clicked.connect(self.__presenter.close_presenter)
        self.calculate_button.clicked.connect(self.__set_days_of_month_on_bottom_axis)
        self.calculate_button.clicked.connect(self.__presenter.calculate_economic_day_summaries)
        self.calculate_button.clicked.connect(lambda: self.vertical_axes_combo_box.setDisabled(False))
        self.calculate_button.clicked.connect(lambda: self.__set_graph_title(self.NET_PROFIT_ITEM))
        self.calculate_button.clicked.connect(lambda: self.vertical_axes_combo_box.setCurrentText(self.NET_PROFIT_ITEM))
        self.vertical_axes_combo_box.currentTextChanged.connect(self.__presenter.change_vertical_axis_and_plot_values)
        self.vertical_axes_combo_box.currentTextChanged.connect(self.__set_graph_title)

    def __set_days_of_month_on_bottom_axis(self):
        self.__set_calculated_month_date()
        bottom_axis: AxisItem = self.plot_widget.getPlotItem().getAxis('bottom')
        bottom_axis.setTicks(self.__generate_day_of_month_ticks())
        self.plot_widget.getPlotItem().getViewBox().setRange(
            xRange=(1, self.__get_last_day_of_month())
        )

    def __set_calculated_month_date(self):
        qdate: QDate = self.month_date_edit.date()
        self.__calculated_month_date = date(day=1, month=qdate.month(), year=qdate.year())

    def __generate_day_of_month_ticks(self):
        ticks = {}
        current_date = self.__calculated_month_date

        while current_date.month == self.__calculated_month_date.month:
            ticks[current_date.day] = str(current_date.day)

            current_date = current_date + timedelta(days=1)
        return [ticks.items()]

    def __get_last_day_of_month(self) -> int:
        if self.__calculated_month_date.month == 12:
            next_month = 1
        else:
            next_month = self.__calculated_month_date.month + 1

        if next_month == 1:
            first_date_next_month = date(day=1, month=1, year=self.__calculated_month_date.year + 1)
        else:
            first_date_next_month = date(day=1, month=next_month, year=self.__calculated_month_date.year)

        return (first_date_next_month - timedelta(days=1)).day

    def __set_graph_title(self, new_text: str):
        if self.__calculated_month_date is None:
            return
        self.plot_widget.getPlotItem() \
            .setTitle(f'<span style="color: #0F172A; font-size: 14px; font-weight: bold;">{new_text} en {self.__get_selected_month_as_word()} '
                      f'de {self.__calculated_month_date.year}</span>')

    def __get_selected_month_as_word(self) -> str:
        month = self.__calculated_month_date.month
        if month == 1:
            return 'Enero'
        elif month == 2:
            return 'Febrero'
        elif month == 3:
            return 'Marzo'
        elif month == 4:
            return 'Abril'
        elif month == 5:
            return 'Mayo'
        elif month == 6:
            return 'Junio'
        elif month == 7:
            return 'Julio'
        elif month == 8:
            return 'Agosto'
        elif month == 9:
            return 'Septiembre'
        elif month == 10:
            return 'Octubre'
        elif month == 11:
            return 'Noviembre'
        else:
            return 'Diciembre'

    def get_selected_month_date(self):
        qdate: QDate = self.month_date_edit.date()
        return date(day=1, month=qdate.month(), year=qdate.year())

    def disable_gui(self, disable: bool):
        self.tool_bar_frame.setDisabled(disable)
        self.main_content_frame.setDisabled(disable)

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

    def plot_values(self, x_days_values: list, y_values: list):
        self.plot_widget.getPlotItem().clear()
        if not y_values:
            return

        min_left_axis = min(y_values) if min(y_values) < 0 else 0
        self.__set_left_axis_limits(y_range=(min_left_axis, max(y_values)))

        self.__draw_graph_lines(x_days_values, y_values)
        self.__draw_graph_points(x_days_values, y_values)

    def __set_left_axis_limits(self, y_range: tuple):
        self.plot_widget.getPlotItem().getViewBox().setRange(
            yRange=y_range
        )

    def __draw_graph_lines(self, month_axis: list, y_axis: list):
        plot_curve_item = PlotCurveItem()
        plot_curve_item.setData(month_axis, y_axis,
                                pen=mkPen({'color': '#0F6FFF', 'width': 2.5}),
                                antialias=True)
        self.plot_widget.addItem(plot_curve_item)

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
        self.plot_widget.addItem(scatter_plot_item)