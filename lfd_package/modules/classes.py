"""
Module description:
    These classes initialize the operating parameters of each element of the
    energy system (mCHP, TES, Aux Boiler, Energy Demand)
"""

import pathlib, pandas as pd, numpy as np
from lfd_package.modules.__init__ import ureg


class CHP:
    def __init__(self, capacity=None, heat_power=None, turn_down_ratio=None, part_load=None, cost=None):
        """
        This class defines the operating parameters of the mCHP system.

        Parameters
        ----------
        capacity: float
            Size of the CHP system in kW (kilowatts)
        heat_power: float
            The heat-to-power ratio of the CHP system
        turn_down_ratio: float
            The ratio of the maximum capacity to minimum capacity
        part_load: numpy.ndarray
            An array where column 0 is the partial load as a percent of max
            capacity and column 1 is the associated mCHP efficiency
        cost: float
            The incremental installation cost of the CHP system (includes material cost and labor)
        """
        self.cap = capacity * ureg.kW
        self.hp = heat_power
        self.td = turn_down_ratio
        self.pl = part_load
        self.cost = cost * (1/ureg.kW)
        try:
            chp_min = self.cap / self.td
        except ZeroDivisionError:
            chp_min = 0
        self.min = chp_min


class AuxBoiler:
    def __init__(self, capacity=None, efficiency=None, turn_down_ratio=None):
        """
        This class defines the operating parameters of the Auxiliary Boiler.

        Parameters
        ----------
        capacity: float
            Size of the boiler in MMBtu/hr (Btu = British Thermal Units)
        efficiency: float
            The rated efficiency of the boiler
        turn_down_ratio: float
            The ratio of the maximum capacity to minimum capacity
        """
        self.cap = capacity * (ureg.Btu / ureg.hour)
        self.eff = efficiency
        self.td = turn_down_ratio
        try:
            ab_min = self.cap / self.td
        except ZeroDivisionError:
            ab_min = 0
        self.min = ab_min


class EnergyDemand:
    def __init__(self, file_name='default_file.csv', electric_cost=None, fuel_cost=None):
        """
        This class defines the electricity and heating demand of a mid-
        rise apartment building.

        The data is imported from the file 'default_file.csv'
        using pandas.

        Parameters
        ----------
        file_name: string
            File name of the .csv file with the load profile data. This can be changed from the
            default value by modifying the name in the .yaml file.
        electric_cost: float
            Cost of electricity in $/kWh
        fuel_cost: float
            Cost of electricity in $/MMBtu
        """
        # Reads load profile data from .csv file
        cwd = pathlib.Path(__file__).parent.parent.resolve() / 'input_files'
        self.demand_file_name = file_name
        df = pd.read_csv(cwd / file_name)

        # Plucks electrical load data from the file using row and column locations
        electric_demand_df = df.iloc[9:, 16]
        electric_demand_hourly = electric_demand_df.to_numpy()

        # Plucks thermal load data from the file using row and column locations
        heating_demand_df = df.iloc[9:, 29]
        heating_demand_hourly = heating_demand_df.to_numpy()

        # Energy Costs
        self.el_cost = electric_cost * (1/ureg.kWh)
        self.fuel_cost = fuel_cost * (1/ureg.megaBtu)

        def convert_numpy_to_float(array=None):
            float_list = []
            for item in array:
                f = float(item)
                float_list.append(f)
            float_array = np.array(float_list, dtype=float)
            return float_array

        self.hl = convert_numpy_to_float(heating_demand_hourly) * ureg.Btu
        self.el = convert_numpy_to_float(electric_demand_hourly) * ureg.kWh

        def sum_annual_demand(array=None):
            demand_items = []
            for demand in array:
                assert demand >= 0
                demand_items.append(demand)
            demand_sum = sum(demand_items)
            return demand_sum

        self.annual_el = sum_annual_demand(array=self.el)
        self.annual_hl = sum_annual_demand(array=self.hl)

        def create_demand_curve_array(array=None):
            assert array.ndim == 1
            total_days = len(array) / 24
            reverse_sort_array = np.sort(array.magnitude, axis=0)
            sorted_demand_array = reverse_sort_array[::-1]
            percent_days = []
            for i, k in enumerate(array):
                percent = (i / 24) / total_days
                percent_days.append(percent)
            percent_days_array = np.array(percent_days)
            return percent_days_array, sorted_demand_array

        self.el_demand_curve_array = create_demand_curve_array(self.el)
        self.hl_demand_curve_array = create_demand_curve_array(self.hl)

        def size_mchp_system(array=None):
            assert array.ndim == 1
            percent_days_array, sorted_demand_array = create_demand_curve_array(array=array)
            prod_array = np.multiply(percent_days_array, sorted_demand_array)
            max_value = np.amax(prod_array)
            return max_value

        self.el_mchp_size_rec = size_mchp_system(self.el) * ureg.kW
        self.hl_mchp_size_rec = size_mchp_system(self.hl) * ureg.Btu


class TES:
    def __init__(self, capacity=None, start=None, discharge=None, cost=None):
        """
        This class defines the operating parameters of the TES (Thermal energy storage) system
        TODO: Consider adding upper and lower limits for power extracted
        TODO: Change upper and lower limits for power extraction when SOC is 0 or 1

        capacity: float
            Size of the TES system in Btu (Btu = British Thermal Units)
        cost: float
            The incremental installation cost of the TES system (includes material cost and labor)
        """
        self.cap = capacity * ureg.Btu
        self.start = start * ureg.Btu
        self.discharge = discharge * ureg('Btu/hr')
        self.cost = cost * (1/ureg.kWh)
