"""
Module description:
    These functions calculate the desired size of the CHP and TES systems
"""

import numpy as np
from lfd_package.modules.__init__ import ureg, Q_
from lfd_package.modules import thermal_storage as storage


def create_demand_curve_array(array=None):
    """
    Docstring updated 9/24/2022

    Creates two 1D numpy arrays containing percent total days (days / days in 1 year)
    and associated energy demand data (thermal or electrical), respectively.

    Used in the max_rect_chp_size function for CHP sizing using the Max Rectangle (MR) method.

    Parameters
    ----------
    array: numpy.ndarray (Quantity)
        One dimensional numpy array containing energy demand data (thermal or electrical).
        Items in the array are Quantity values.

    Returns
    -------
    percent_days_array: numpy.ndarray
        1D array of percent total days (day in year / total days in 1 year) values.
    sorted_demand_array: numpy.ndarray (Quantity)
        1D array of energy demand data associated with the percent-days data. Contains
        Quantity values.
    """
    if array is not None:
        assert array.ndim == 1
        reverse_sort_array = np.sort(array, axis=0)
        sorted_demand_array = reverse_sort_array[::-1]
        percent_days = []
        for i, k in enumerate(array):
            percent = ((i+1) / len(array))*100
            percent_days.append(percent)
        percent_days_array = np.array(percent_days)
        return percent_days_array, sorted_demand_array


def electrical_output_to_fuel_consumption(electrical_output=None):
    """
    Docstring updated 9/24/2022

    Calculates approximate CHP fuel consumption for a given electrical output.
    The constants are from a linear fit of CHP data (<100kW) created in Excel.
    The data used for the fit are derived from the CHP TAP's eCatalog. The
    R^2 value of the fit is 0.99. Link to eCatalog: https://chp.ecatalog.ornl.gov

    Used in the calc_min_pes_chp_size function

    Parameters
    ----------
    electrical_output: Quantity (float)
        Electrical output of CHP in units of kW

    Returns
    -------
    fuel_consumption_kw: Quantity (float)
        Approximate fuel consumption of CHP in units of kW thermal
    """
    if electrical_output is not None:
        assert electrical_output.units == ureg.kW

        if electrical_output.magnitude == 0:
            return Q_(0, ureg.kW)
        else:
            a = 3.6376
            assert electrical_output.units == ureg.kW
            fuel_consumption_kw = (a * electrical_output.magnitude) * ureg.kW
            return fuel_consumption_kw


def electrical_output_to_thermal_output(electrical_output=None):
    """
    Docstring updated 9/24/2022

    Calculates approximate CHP thermal output for a given electrical output.
    The constants are from a linear fit of CHP data (<100kW)
    created in Excel. The data for the fit are derived from the CHP TAP's
    eCatalog. The R^2 value of the fit is 0.97. Link to eCatalog:
    https://chp.ecatalog.ornl.gov

    Used in the calc_min_pes_chp_size function.
    Used in the calc_avg_efficiency, elf_calc_hourly_heat_generated, and
    tlf_calc_hourly_heat_generated functions in the chp.py module

    Parameters
    ----------
    electrical_output: Quantity (float)
        Electrical output of CHP in units of kW

    Returns
    -------
    thermal_output_kw: Quantity (float)
        Approximate thermal output of CHP in units of kW
    """
    if electrical_output is not None:
        assert electrical_output.units == ureg.kW

        if electrical_output.magnitude == 0:
            return Q_(0, ureg.kW)
        else:
            a = 1.8721
            thermal_output_kw = (a * electrical_output.magnitude) * ureg.kW
            return thermal_output_kw


def thermal_output_to_electrical_output(thermal_output=None):
    """
    Docstring updated 9/24/2022

    Calculates the approximate CHP electrical output for a given thermal output.
    The constants are from a linear fit of CHP data (<100kW)
    in excel. The data is derived from the CHP TAP eCatalog. The R^2 value of
    the fit is 0.97. eCatalog link: https://chp.ecatalog.ornl.gov

    Used in the tlf_calc_electricity_bought_and_generated function in the
    chp.py module

    Parameters
    ----------
    thermal_output: Quantity (float)
        Thermal output of CHP in units of kW (thermal)

    Returns
    -------
    electrical_output_kw: Quantity (float)
        Approximate electrical output of CHP in units of kW
    """
    if thermal_output is not None:
        assert thermal_output.units == ureg.kW

        if thermal_output.magnitude == 0:
            return Q_(0, ureg.kW)
        else:
            a = 0.5188
            electrical_output_kw = (thermal_output.magnitude * a) * ureg.kW
            if electrical_output_kw.magnitude <= 0:
                return Q_(0, ureg.kW)
            else:
                return electrical_output_kw


def size_chp(load_following_type=None, class_dict=None):
    """
    Docstring updated 9/24/2022

    Sizes the CHP system using either the max_rect_chp_size function or the
    calc_min_pes_chp_size function as needed depending on operating strategy (load
    following type) and/or presence of net metering.

    Used in chp.py module

    Parameters
    ----------
    load_following_type: string
        Reads as either "ELF" or "TLF" depending on whether the operating
        strategy is electrical load following or thermal load following,
        respectively.
    demand: EnergyDemand class
        Initialized class data (see command_line.py module)
    ab: AuxBoiler class
        Initialized class data (see command_line.py module)

    Returns
    -------
    chp_size: Quantity (float)
        Recommended size of CHP system in units of kW
    """
    args_list = [load_following_type, class_dict]
    if any(elem is None for elem in args_list) is False:
        if load_following_type is "PP":
            chp_size = calc_min_pes_chp_size(class_dict=class_dict)[0]
        elif load_following_type is "ELF":
            chp_size = calc_max_rect_chp_size(array=class_dict['demand'].el)
        elif load_following_type is "TLF":
            thermal_size = (calc_max_rect_chp_size(array=class_dict['demand'].hl)).to(ureg.kW)
            chp_size = thermal_output_to_electrical_output(thermal_output=thermal_size)
        else:
            raise Exception("Error in size_chp function in module sizing_calcs.py")

        # Convert units
        if chp_size.units != ureg.kW:
            chp_size.to(ureg.kW)

        return chp_size


# TODO: Turn into static CHP class method
def calc_max_rect_chp_size(array=None):
    """
    Docstring updated 9/24/2022

    Calculates the recommended CHP size in kW based on the Maximum Rectangle (MR)
    sizing method. The input array is either electrical or thermal demand.

    Used in the size_chp function

    Parameters
    ----------
    array: numpy.ndarray
        One 1D numpy array containing either electrical or thermal energy demand data.
        Items in this array are Quantity values with units of either kW or Btu/hr.

    Returns
    -------
    max_value: Quantity (float)
        The recommended size (either thermal or electrical) of the CHP system. Units
        will be either kW or Btu/hr.
    """
    if array is not None:
        assert array.ndim == 1
        percent_days_array, sorted_demand_array = create_demand_curve_array(array=array)
        prod_array = np.multiply(percent_days_array, sorted_demand_array)
        max_index = np.argmax(prod_array)
        max_value = sorted_demand_array[max_index]
        return max_value


def calc_min_pes_chp_size(class_dict=None):
    """
    Docstring updated 9/24/2022

    Recommends a CHP system size using the minimum Primary Energy Savings
    (PES) method. A high PES value indicates that the associated CHP size
    saves the maximum energy compared to the baseline case. A low PES value
    indicates that the associated CHP size is the most profitable (but saves
    the least energy compared to the baseline case)

    Used in the size_chp function

    Parameters
    ----------
    demand: EnergyDemand class
        Initialized class data (see command_line.py module)
    ab: AuxBoiler class
        Initialized class data (see command_line.py module)

    Returns
    -------
    max_pes_size: Quantity (float)
        Recommended size of CHP system in units of kW electrical
    """
    args_list=[class_dict]
    if any(elem is None for elem in args_list) is False:
        chp_size_list = list(range(10, 105, 5)) * ureg.kW

        grid_eff = class_dict['demand'].grid_efficiency
        size_list = []
        pes_list = []

        for size in chp_size_list:
            max_fuel_consumption = electrical_output_to_fuel_consumption(electrical_output=size)
            max_thermal_output = electrical_output_to_thermal_output(electrical_output=size)
            electrical_eff = size/max_fuel_consumption
            thermal_eff = max_thermal_output/max_fuel_consumption

            nominal_electrical_eff = electrical_eff / grid_eff
            nominal_thermal_eff = thermal_eff / class_dict['ab'].eff
            pes = 1 - (1/(nominal_thermal_eff + nominal_electrical_eff))

            size_list.append(size)
            pes_list.append(pes)

        # TODO: Have function output both min and max values for sizing
        min_pes_value = min(pes_list)
        max_pes_value = max(pes_list)
        min_pes_index = pes_list.index(min_pes_value)
        max_pes_index = pes_list.index(max_pes_value)
        min_pes_size = size_list[min_pes_index]
        max_pes_size = size_list[max_pes_index]

        return min_pes_size, max_pes_size


def size_tes(chp_gen_hourly_kwh_dict=None, chp_size=None, load_following_type=None, class_dict=None):
    """
    TODO: Need to validate calculation, check that its reasonable
    Requires hourly heat demand data, hourly CHP heating demand coverage, and hourly heat generation by CHP.

    Sizes TES by maximizing the system efficiency. Uses uncovered heat demand values and excess chp heat
    generation values. Chooses the smallest of these two values for each day and creates a list of those
    minimums. Then chooses the max value in that list as the recommended size.

    Returns
    -------

    """
    # Create empty lists
    uncovered_heat_demand_hourly = []
    daily_uncovered_heat_btu_list = []
    excess_chp_heat_gen_hourly = []
    daily_excess_chp_heat_btu_list = []
    list_comparison_min_values = []

    # For unit management in pint
    hour_unit = Q_(1, ureg.hour)

    # Pull needed data
    if load_following_type == "TLF":
        # TODO: Assume chp runs all the time
        hourly_excess_and_deficit_list = \
            [(electrical_output_to_thermal_output(chp_size)).to(ureg.Btu / ureg.hour) - dem for dem in class_dict['demand'].hl]
    else:
        hourly_excess_and_deficit_list = \
            storage.calc_excess_and_deficit_chp_heat_gen(chp_gen_hourly_kwh_dict=chp_gen_hourly_kwh_dict,
                                                         load_following_type=load_following_type, class_dict=class_dict)
    assert isinstance(hourly_excess_and_deficit_list, list)
    assert hourly_excess_and_deficit_list[0].units == ureg.Btu / ureg.hour

    # Separate data into excess generation list and uncovered demand list
    for index, element in enumerate(hourly_excess_and_deficit_list):
        if element.magnitude <= 0:
            uncovered_heat_demand_hourly.append(Q_(abs(element.magnitude), element.units))
            excess_chp_heat_gen_hourly.append(Q_(0, ureg.Btu / ureg.hour))
        elif 0 < element.magnitude:
            uncovered_heat_demand_hourly.append(Q_(0, ureg.Btu / ureg.hour))
            excess_chp_heat_gen_hourly.append(Q_(abs(element.magnitude), element.units))
        else:
            raise Exception('Error in sizing_calcs.py function, size_tes()')

    # Turn hourly lists into daily sums
    assert len(uncovered_heat_demand_hourly) == len(excess_chp_heat_gen_hourly)
    for index in range(24, len(uncovered_heat_demand_hourly) + 1, 24):
        daily_uncovered_heat_btu_hour = sum(uncovered_heat_demand_hourly[(index - 24):index])
        daily_uncovered_heat_btu = (daily_uncovered_heat_btu_hour * hour_unit).to(ureg.Btu)
        daily_uncovered_heat_btu_list.append(daily_uncovered_heat_btu)

        daily_excess_heat_btu_hour = sum(excess_chp_heat_gen_hourly[(index - 24):index])
        daily_excess_heat_btu = (daily_excess_heat_btu_hour * hour_unit).to(ureg.Btu)
        daily_excess_chp_heat_btu_list.append(daily_excess_heat_btu)

    # Compare the two lists and pick the min for each day
    assert len(daily_excess_chp_heat_btu_list) == len(daily_uncovered_heat_btu_list)
    for index in range(len(daily_excess_chp_heat_btu_list)):
        if daily_excess_chp_heat_btu_list[index] <= daily_uncovered_heat_btu_list[index]:
            list_comparison_min_values.append(daily_excess_chp_heat_btu_list[index])
        elif daily_uncovered_heat_btu_list[index] < daily_excess_chp_heat_btu_list[index]:
            list_comparison_min_values.append(daily_uncovered_heat_btu_list[index])
        else:
            raise Exception('Error in sizing_calcs.py function, size_tes()')

    assert len(list_comparison_min_values) == len(daily_excess_chp_heat_btu_list)

    # Search the resulting list of min values for the maximum, aka the TES size
    tes_size_btu = max(list_comparison_min_values)
    assert list_comparison_min_values[0].units == ureg.Btu
    assert tes_size_btu.units == ureg.Btu

    if 0 <= tes_size_btu.magnitude:
        return tes_size_btu
    else:
        raise Exception('TES size is negative - error in size_tes() function')
