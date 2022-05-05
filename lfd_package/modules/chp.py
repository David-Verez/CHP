"""
Module Description:
    Contains functions needed to calculate the demand, electricity cost, and fuel use of
    the micro-chp unit.
"""

import numpy as np
from lfd_package.modules.__init__ import ureg


def calc_hourly_electricity_bought(chp=None, demand=None):
    """
    This function compares mCHP capacity and minimum allowed electrical generation
    with hourly electrical demand. If demand is too high or too low, it calculates
    how much electricity needs to be purchased from the utility each hour.

    Parameters
    ---------
    chp: CHP Class
        contains initialized CHP class data using CLI inputs (see command_line.py)
    demand: EnergyDemand Class
        contains initialized EnergyDemand class data using CLI inputs (see command_line.py)

    Returns
    -------
    utility_bought_list: list
        contains float values for electricity purchased hourly
    """
    if chp is not None and demand is not None:
        # Convert max and min chp output to kWh using data resolution
        data_res = 1 * ureg.hour
        chp_max_kwh = chp.cap * data_res
        chp_min_kwh = chp.min * data_res
        demand_hourly = demand.el

        utility_bought_list = []

        for d in demand_hourly:
            # Verifies acceptable input value range
            assert d >= 0

            if chp_min_kwh <= d <= chp_max_kwh:
                bought = 0 * ureg.kWh
                utility_bought_list.append(bought)
            elif d < chp_min_kwh:
                bought = d
                utility_bought_list.append(bought)
            elif chp_max_kwh < d:
                bought = abs(d - chp_max_kwh)
                utility_bought_list.append(bought)
            else:
                raise Exception("Error in ELF calc_utility_electricity_needed function")

        return utility_bought_list


def calc_annual_electric_cost(chp=None, demand=None):
    """
    Calculates the annual cost of electricity bought from the local utility.

    This function calls the calc_utility_electricity_needed function and uses the
    calculated utility electricity needed. Assumes that energy dispatch for the
    mCHP system is electric load following (ELF)

    Parameters
    ---------
    chp: CHP Class
        contains initialized CHP class data using CLI inputs (see command_line.py)
    demand: EnergyDemand Class
        contains initialized EnergyDemand class data using CLI inputs (see command_line.py)

    Returns
    -------
    annual_cost: float
        The total annual cost of electricity bought from the local utility
    """
    if demand is not None:
        electric_rate = demand.el_cost

        total_bought = sum(calc_hourly_electricity_bought(chp=chp, demand=demand))
        annual_cost = total_bought * electric_rate

        return annual_cost


def calc_hourly_efficiency(chp=None, demand=None):
    """
    Calculates the hourly mCHP efficiency using part-load electrical efficiency data.

    Note: This can be improved by linearizing the array for a more accurate efficiency value

    Parameters
    ---------
    chp: CHP Class
        contains initialized CHP class data using CLI inputs (see command_line.py)
    demand: EnergyDemand Class
        contains initialized EnergyDemand class data using CLI inputs (see command_line.py)

    Returns
    -------
    eff_list: list
        Array of efficiency values from the chp_pl array that correspond to the
        partload closest to the actual partload during that hour.
    """
    if chp is not None and demand is not None:
        # Convert chp max output to kWh using data resolution
        data_res = 1 * ureg.hour
        chp_max_kwh = chp.cap * data_res
        chp_pl = chp.pl

        demand_hourly = demand.el

        rows = demand_hourly.shape[0]
        eff_list = []

        for i in range(rows):
            demand = demand_hourly[i]
            partload_actual = demand/chp_max_kwh

            # Grabs the first column and calculates difference
            part_loads = chp_pl[:, 0]
            desired_shape = np.shape(part_loads)
            actual_load_array = np.full(shape=desired_shape, fill_value=partload_actual.magnitude)
            diff = np.abs(part_loads, actual_load_array)
            idx = diff.argmin()

            part_effs = chp_pl[idx, 1]
            eff_list.append(part_effs)
        return eff_list


def calc_hourly_generated_electricity(chp=None, demand=None):
    """
    Calculates electricity generated by the mCHP unit each hour

    Parameters
    ---------
    chp: CHP Class
        contains initialized CHP class data using CLI inputs (see command_line.py)
    demand: EnergyDemand Class
        contains initialized EnergyDemand class data using CLI inputs (see command_line.py)

    Returns
    -------
    generated_list: list
        Contains values for the amount of electricity generated each hour
    """
    if chp is not None and demand is not None:
        demand_hourly = demand.el
        demand_bought_hourly = calc_hourly_electricity_bought(chp=chp, demand=demand)

        generated_list = []

        for i in range(len(demand_hourly)):
            generated = abs(demand_bought_hourly[i] - demand_hourly[i])
            generated_list.append(generated)

        return generated_list


def calc_hourly_heat_generated(chp=None, demand=None):
    """
    Uses heat to power ratio and hourly electricity generated to calculate
    hourly thermal output of the mCHP unit.

    Parameters
    ---------
    chp: CHP Class
        contains initialized CHP class data using CLI inputs (see command_line.py)
    demand: EnergyDemand Class
        contains initialized EnergyDemand class data using CLI inputs (see command_line.py)

    Returns
    -------
    hourly_heat: list
        Hourly thermal output of the mCHP unit
    """
    if chp is not None and demand is not None:
        heat_to_power = chp.hp
        electricity_generated = calc_hourly_generated_electricity(chp=chp, demand=demand)
        hourly_heat = []

        for i in range(len(electricity_generated)):
            electricity_generated[i].to(ureg.kWh)
            heat_kwh = heat_to_power * electricity_generated[i]
            heat = heat_kwh.to(ureg.Btu)
            hourly_heat.append(heat)

        return hourly_heat


def calculate_annual_fuel_use(chp=None, demand=None):
    """
    Uses hourly electrical efficiency values (electricity generated / fuel used)
    and hourly electricity generated to calculate fuel use for each hour.

    Assumes that energy dispatch for the mCHP system is electric load
    following (ELF).

    Parameters
    ---------
    chp: CHP Class
        contains initialized CHP class data using CLI inputs (see command_line.py)
    demand: EnergyDemand Class
        contains initialized EnergyDemand class data using CLI inputs (see command_line.py)

    Returns
    -------
    total_fuel: float
        Annual fuel use in Btu.
    """
    if chp is not None and demand is not None:
        efficiency_list = calc_hourly_efficiency(chp=chp, demand=demand)
        electricity_generated = calc_hourly_generated_electricity(chp=chp, demand=demand)

        fuel_use = []

        for i in range(len(efficiency_list)):
            if efficiency_list[i] is not 0:
                electricity_gen_kwh = electricity_generated[i]
                fuel_kwh = electricity_gen_kwh / efficiency_list[i]
                fuel_btu = fuel_kwh.to(ureg.Btu)
                fuel_use.append(fuel_btu)
            else:
                fuel_use.append(0 * ureg.Btu)

        total_fuel = sum(fuel_use)
        return total_fuel


def calc_annual_fuel_cost(chp=None, demand=None):
    """
    Calculates the annual fuel cost from the annual fuel use of the mCHP unit

    Parameters
    ----------
    chp: CHP Class
        contains initialized CHP class data using CLI inputs (see command_line.py)
    demand: EnergyDemand Class
        contains initialized EnergyDemand class data using CLI inputs (see command_line.py)

    Returns
    -------
    annual_fuel_cost: float
        annual fuel cost of the mCHP unit
    """
    annual_fuel_use_btu = calculate_annual_fuel_use(chp=chp, demand=demand)
    annual_fuel_use_mmbtu = annual_fuel_use_btu.to(ureg.megaBtu)
    annual_fuel_cost = annual_fuel_use_mmbtu * demand.fuel_cost
    return annual_fuel_cost


if __name__ == '__main__':
    print('stuff')
