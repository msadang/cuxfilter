import cudf
import dask_cudf
from typing import Tuple

from ..core_chart import BaseChart
from ....layouts import chart_view


class BaseStackedLine(BaseChart):
    """
        No datatiles support in non_data_tiles plot charts

        If dataset size is greater than a few thousand points,
        scatter geos can crash the browser tabs, and is only recommended
        with datashader plugin, in which case an image is
        rendered instead of points on canvas
    """

    reset_event = None
    x_range: Tuple = None
    y_range: Tuple = None
    use_data_tiles = False
    y: list = []
    colors: list = []

    @property
    def y_dtype(self):
        """
        overwriting the y_dtype property from BaseChart for stackedLines where
        self.y is a list of columns
        """
        if isinstance(self.source, (cudf.DataFrame, dask_cudf.DataFrame)):
            return self.source[self.y[0]].dtype
        return None

    def __init__(
        self,
        x,
        y=[],
        data_points=100,
        add_interaction=True,
        colors=[],
        step_size=None,
        step_size_type=int,
        width=800,
        height=400,
        title="",
        timeout=100,
        legend=True,
        legend_position="center",
        x_axis_tick_formatter=None,
        y_axis_tick_formatter=None,
        **library_specific_params,
    ):
        """
        Description:

        -------------------------------------------
        Input:
            x,
            y
            data_points
            add_interaction
            colors
            step_size
            step_size_type
            width
            height
            title
            timeout
            legend
            legend_position
            x_axis_tick_formatter
            y_axis_tick_formatter
            **library_specific_params
        -------------------------------------------

        Ouput:

        """
        self.x = x
        if not isinstance(y, list):
            raise TypeError("y must be a list of column names")
        if len(y) == 0:
            raise ValueError("y must not be empty")
        self.y = y
        self.data_points = data_points
        self.add_interaction = add_interaction
        self.stride = step_size
        if not isinstance(colors, list):
            raise TypeError("colors must be a list of colors")
        self.colors = colors
        self.stride_type = step_size_type
        self.title = title
        self.timeout = timeout
        self.legend = legend
        self.legend_position = legend_position
        self.x_axis_tick_formatter = x_axis_tick_formatter
        self.y_axis_tick_formatter = y_axis_tick_formatter
        self.library_specific_params = library_specific_params
        self.width = width
        self.height = height

    def initiate_chart(self, dashboard_cls):
        """
        Description:

        -------------------------------------------
        Input:
        data: cudf DataFrame
        -------------------------------------------
        """
        for _y in self.y:
            if self.y_dtype != dashboard_cls._cuxfilter_df.data[_y].dtype:
                raise TypeError("All y columns should be of same type")

        if self.x_range is None:
            self.x_range = (
                dashboard_cls._cuxfilter_df.data[self.x].min(),
                dashboard_cls._cuxfilter_df.data[self.x].max(),
            )
        if self.y_range is None:
            # cudf_df[['a','b','c']].min().min() gives min value
            # between all values in columns a,b and c
            self.y_range = (
                dashboard_cls._cuxfilter_df.data[self.y].min().min(),
                dashboard_cls._cuxfilter_df.data[self.y].max().max(),
            )
        self.calculate_source(dashboard_cls._cuxfilter_df.data)
        self.generate_chart()
        self.add_events(dashboard_cls)

    def view(self):
        return chart_view(self.chart, width=self.width)

    def calculate_source(self, data):
        """
        Description:

        -------------------------------------------
        Input:
        data = cudf.DataFrame
        -------------------------------------------

        Ouput:
        """
        self.format_source_data(data)

    def get_selection_geometry_callback(self, dashboard_cls):
        """
        Description: generate callback for stacked line
            selection event (only along x-axis)
        -------------------------------------------
        Input:

        -------------------------------------------

        Ouput:

        """

        def selection_callback(event):
            xmin, xmax = self._xaxis_dt_transform(
                (event.geometry["x0"], event.geometry["x1"])
            )
            if dashboard_cls._active_view != self.name:
                # reset previous active view and
                # set current chart as active view
                dashboard_cls._reset_current_view(new_active_view=self)
                self.source = dashboard_cls._cuxfilter_df.data

            self.x_range = (xmin, xmax)

            query = f"@{self.x}_min<={self.x}<=@{self.x}_max"
            temp_str_dict = {
                **dashboard_cls._query_str_dict,
                **{self.name: query},
            }
            temp_local_dict = {
                **dashboard_cls._query_local_variables_dict,
                **{self.x + "_min": xmin, self.x + "_max": xmax},
            }

            temp_data = dashboard_cls._query(
                dashboard_cls._generate_query_str(temp_str_dict),
                temp_local_dict,
            )
            # reload all charts with new queried data (cudf.DataFrame only)
            dashboard_cls._reload_charts(
                data=temp_data, ignore_cols=[self.name]
            )
            self.reload_chart(temp_data, False)
            # self.reload_chart(temp_data, False)
            del temp_data

        return selection_callback

    def compute_query_dict(self, query_str_dict, query_local_variables_dict):
        """
        Description:

        -------------------------------------------
        Input:
        query_dict = reference to dashboard.__cls__.query_dict
        -------------------------------------------

        Ouput:
        """
        if self.x_range is not None and self.y_range is not None:
            query_str_dict[
                self.name
            ] = f"@{self.x}_min<={self.x}<=@{self.x}_max"
            temp_local_dict = {
                self.x + "_min": self.x_range[0],
                self.x + "_max": self.x_range[1],
            }
            query_local_variables_dict.update(temp_local_dict)
        else:
            query_str_dict.pop(self.name, None)
            for key in [self.x + "_min", self.x + "_max"]:
                query_local_variables_dict.pop(key, None)

    def add_events(self, dashboard_cls):
        """
        Description:

        -------------------------------------------
        Input:

        -------------------------------------------

        Ouput:
        """
        if self.add_interaction:
            self.add_selection_geometry_event(
                self.get_selection_geometry_callback(dashboard_cls)
            )
        if self.reset_event is not None:
            self.add_reset_event(dashboard_cls)

    def add_reset_event(self, dashboard_cls):
        """
        Description:

        -------------------------------------------
        Input:

        -------------------------------------------

        Ouput:
        """

        def reset_callback(event):
            if dashboard_cls._active_view != self.name:
                # reset previous active view and
                # set current chart as active view
                dashboard_cls._reset_current_view(new_active_view=self)
                self.source = dashboard_cls._cuxfilter_df.data
            self.x_range = None
            self.y_range = None
            dashboard_cls._query_str_dict.pop(self.name, None)
            dashboard_cls._reload_charts()

        # add callback to reset chart button
        self.add_event(self.reset_event, reset_callback)

    def query_chart_by_range(
        self,
        active_chart: BaseChart,
        query_tuple,
        datatile=None,
        query="",
        local_dict={},
    ):
        """
        Description:

        -------------------------------------------
        Input:
            1. active_chart: chart object of active_chart
            2. query_tuple: (min_val, max_val) of the query [type: tuple]
            3. datatile: None in case of Gpu Geo Scatter charts
        -------------------------------------------

        Ouput:
        """
        min_val, max_val = query_tuple
        final_query = f"@min_val<={active_chart.x}<=@max_val"
        if len(query) > 0:
            final_query += f" and {query}"
        self.reload_chart(
            self.source.query(final_query, local_dict), False,
        )

    def query_chart_by_indices(
        self,
        active_chart: BaseChart,
        old_indices,
        new_indices,
        datatile=None,
        query="",
        local_dict={},
    ):
        """
        Description:

        -------------------------------------------
        Input:
            1. active_chart: chart object of active_chart
            2. query_tuple: (min_val, max_val) of the query [type: tuple]
            3. datatile: None in case of Gpu Geo Scatter charts
        -------------------------------------------

        Ouput:
        """
        if "" in new_indices:
            new_indices.remove("")
        if len(new_indices) == 0:
            # case: all selected indices were reset
            # reset the chart
            final_query = query
        elif len(new_indices) == 1:
            final_query = f"{active_chart.x}=={str(float(new_indices[0]))}"
            if len(query) > 0:
                final_query += f" and {query}"
        else:
            new_indices_str = ",".join(map(str, new_indices))
            final_query = f"{active_chart.x} in ({new_indices_str})"
            if len(query) > 0:
                final_query += f" and {query}"

        self.reload_chart(
            self.source.query(final_query, local_dict)
            if len(final_query) > 0
            else self.source,
            False,
        )

    def add_selection_geometry_event(self, callback):
        """
        Description:

        -------------------------------------------
        Input:

        -------------------------------------------

        Ouput:
        """

        # ('function to be overridden by library specific extensions')

    def reset_chart_geometry_ranges(self):
        """
        Description:

        -------------------------------------------
        Input:

        -------------------------------------------

        Ouput:
        """

        # ('function to be overridden by library specific extensions')
