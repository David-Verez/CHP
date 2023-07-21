"""
Module Description:
    Contains functions needed to calculate the demand, electricity cost, and fuel use of
    the micro-chp unit for both electrical load following (ELF) and thermal load following
    (TLF) cases. Also accounts for whether net metering is permitted by the local utility.
TODO: Add function that calculates the percent annual runtime of the CHP unit
"""

from lfd_package.modules import sizing_calcs as sizing
from lfd_package.modules.__init__ import ureg, Q_


def calc_hourly_fuel_use(chp_gen_hourly_btuh=None, chp_size=None, load_following_type=None, class_dict=None):
    """
    Docstring updated 9/24/2022

    Uses average electrical efficiency and average CHP electricity generation to calculate
    annual fuel use and annual fuel costs.

    Used in the command_line.py module

    Parameters
    ---------
    ab: AuxBoiler Class
        contains initialized class data using CLI inputs (see command_line.py)
    chp: CHP Class
        contains initialized class data using CLI inputs (see command_line.py)
    demand: EnergyDemand Class
        contains initialized class data using CLI inputs (see command_line.py)
    load_following_type: string
        specifies whether calculation is for electrical load following (ELF) state
        or thermal load following (TLF) state.

    Returns
    -------
    annual_fuel_use_btu: Quantity (float)
        Annual fuel use in units of Btu.
    """
    args_list = [chp_size, load_following_type, class_dict]
    if any(elem is None for elem in args_list) is False:
        # Get hourly CHP gen in kWh
        # TODO: Optimize - remove functions called in CLI
        if load_following_type == "PP" or "Peak":
            chp_electric_gen_hourly_kwh = pp_calc_electricity_gen_sold(chp_size=chp_size, class_dict=class_dict)[0]
        elif load_following_type == "ELF":
            chp_electric_gen_hourly_kwh = elf_calc_electricity_generated(chp_size=chp_size, class_dict=class_dict)
        elif load_following_type == "TLF":
            chp_electric_gen_hourly_kwh = tlf_calc_electricity_generated(chp_gen_hourly_btuh=chp_gen_hourly_btuh,
                                                                                    class_dict=class_dict)
        else:
            raise Exception("Error in calc_annual_fuel_use_and_costs function")

        fuel_use_btu_list = []

        # Calculate fuel use
        for index, el in enumerate(chp_electric_gen_hourly_kwh):
            chp_hourly_electric_kw = (el / Q_(1, ureg.hours)).to(ureg.kW)
            fuel_use_hourly_kw = sizing.electrical_output_to_fuel_consumption(chp_hourly_electric_kw)
            fuel_use_hourly_btu = (fuel_use_hourly_kw * Q_(1, ureg.hours)).to(ureg.Btu)
            fuel_use_btu_list.append(fuel_use_hourly_btu)

        return fuel_use_btu_list


def calc_electricity_bought(chp_gen_hourly_kwh=None, chp_size=None, class_dict=None):
    args_list = [chp_gen_hourly_kwh, chp_size, class_dict]
    if any(elem is None for elem in args_list) is False:

        bought_kwh_list = []

        for index, dem_kw in enumerate(class_dict['demand'].el):
            dem_kwh = (dem_kw * Q_(1, ureg.hours)).to(ureg.kWh)
            gen_kwh = chp_gen_hourly_kwh[index]

            if gen_kwh < dem_kwh:
                bought = dem_kwh - gen_kwh
                bought_kwh_list.append(bought)
            else:
                bought = Q_(0, ureg.kWh)
                bought_kwh_list.append(bought)

        return bought_kwh_list


"""
Power Purchase (PP) Functions
"""


def pp_calc_electricity_gen_sold(chp_size=None, class_dict=None):
    args_list = [chp_size, class_dict]
    if any(elem is None for elem in args_list) is False:

        chp_hourly_kwh = (chp_size * Q_(1, ureg.hours)).to(ureg.kWh)
        chp_gen_kwh_list = []
        chp_sold_kwh_list = []

        for dem in class_dict['demand'].el:
            chp_gen_kwh_list.append(chp_hourly_kwh)
            dem_kwh = (dem * Q_(1, ureg.hours)).to(ureg.kWh)
            if dem_kwh <= chp_hourly_kwh:
                chp_sold_kwh_list.append(chp_hourly_kwh - dem_kwh)
            else:
                chp_sold_kwh_list.append(Q_(0, ureg.kWh))

        return chp_gen_kwh_list, chp_sold_kwh_list


def pp_calc_hourly_heat_generated(chp_gen_hourly_kwh=None, class_dict=None):
    args_list = [chp_gen_hourly_kwh, class_dict]
    if any(elem is None for elem in args_list) is False:
        hourly_heat_rate = []

        for i, el_gen_kwh in enumerate(chp_gen_hourly_kwh):
            el_gen = (el_gen_kwh / Q_(1, ureg.hours)).to(ureg.kW)
            heat_kw = sizing.electrical_output_to_thermal_output(el_gen)
            heat = heat_kw.to(ureg.Btu / ureg.hour)
            hourly_heat_rate.append(heat)

        return hourly_heat_rate


"""
ELF Functions
"""


def elf_calc_electricity_generated(chp_size=None, class_dict=None):
    """
    Updated 9/29/2022

    Calculates the electricity generated by the chp system and the electricity bought
    from the local utility to make up the difference.

    This function compares max and min CHP capacity with the hourly electrical
    demand of the building. If demand is above the max or below the min, it calculates
    how much electricity needs to be purchased from the utility for that hour. Also
    calculates electricity generated by the CHP unit each hour.

    Used in the elf_calc_hourly_heat_generated, calc_avg_efficiency,
    calc_annual_fuel_use_and_costs, and calc_annual_electric_cost functions

    Parameters
    ---------
    ab: AuxBoiler Class
        contains initialized class data using CLI inputs (see command_line.py)
    chp: CHP Class
        contains initialized class data using CLI inputs (see command_line.py)
    demand: EnergyDemand Class
        contains initialized class data using CLI inputs (see command_line.py)

    Returns
    -------
    chp_gen_kwh_list: list
        contains Quantity float values for electricity generated hourly in units of kWh
    """
    args_list = [chp_size, class_dict]
    if any(elem is None for elem in args_list) is False:
        chp_gen_kwh_list = []

        chp_min_output = (class_dict['chp'].min_pl * chp_size).to(ureg.kW)

        for dem in class_dict['demand'].el:
            # Verifies acceptable input value range
            assert dem.magnitude >= 0
            dem_kw = dem.to(ureg.kW)

            if chp_min_output <= dem_kw <= chp_size:
                gen = (dem_kw * ureg.hour).to(ureg.kWh)
                chp_gen_kwh_list.append(gen)
            elif dem_kw < chp_min_output:
                gen = 0 * ureg.kWh
                chp_gen_kwh_list.append(gen)
            elif chp_size < dem_kw:
                gen = (chp_size * ureg.hour).to(ureg.kWh)
                chp_gen_kwh_list.append(gen)
            else:
                raise Exception("Error in ELF calc_utility_electricity_needed function")

        return chp_gen_kwh_list


def elf_calc_hourly_heat_generated(chp_gen_hourly_kwh=None, class_dict=None):
    """
    Updated 9/28/2022

    Uses the hourly electricity generated by CHP to calculate the
    hourly thermal output of the CHP unit. Assumes electrical load
    following (ELF) operation.

    Used in the thermal_storage module: calc_excess_and_deficit_heat function

    Parameters
    ---------
    ab: AuxBoiler Class
        contains initialized class data using CLI inputs (see command_line.py)
    chp: CHP Class
        contains initialized class data using CLI inputs (see command_line.py)
    demand: EnergyDemand Class
        contains initialized class data using CLI inputs (see command_line.py)

    Returns
    -------
    hourly_heat_rate: list
        Contains Quantity float values for hourly thermal output of the CHP unit
        in units of Btu/hour
    """
    args_list = [chp_gen_hourly_kwh, class_dict]
    if any(elem is None for elem in args_list) is False:
        hourly_heat_rate = []

        for i, el_gen_kwh in enumerate(chp_gen_hourly_kwh):
            el_gen = (el_gen_kwh / Q_(1, ureg.hours)).to(ureg.kW)
            heat_kw = sizing.electrical_output_to_thermal_output(el_gen)
            heat = heat_kw.to(ureg.Btu / ureg.hour)
            hourly_heat_rate.append(heat)

        return hourly_heat_rate


"""
TLF Functions
"""


def tlf_calc_hourly_heat_chp_tes_soc(chp_size=None, class_dict=None):
    """
    Updated 9/29/2022

    Calculates the hourly heat generated by the CHP system.

    This function compares the thermal demand of the building with the max and
    min heat that can be generated by the chp system. Unlike the ELF case, this
    function allows generation when demand is below chp minimum heat output with
    excess sent to heat storage (TES). Assumes the load following state is thermal
    load following (TLF).

    Used in the thermal_storage module: calc_excess_and_deficit_heat function

    Parameters
    ----------
    ab: AuxBoiler Class
        contains initialized class data using CLI inputs (see command_line.py)
    chp: CHP Class
        contains initialized class data using CLI inputs (see command_line.py)
    demand: EnergyDemand Class
        contains initialized class data using CLI inputs (see command_line.py)

    Returns
    -------
    chp_hourly_heat_rate_list: list
        contains Quantity float values for hourly heat generated by the CHP
        system in units of Btu/hour.
    """
    args_list = [chp_size, class_dict]
    if any(elem is None for elem in args_list) is False:
        chp_min_output = (class_dict['chp'].min_pl * chp_size).to(ureg.kW)

        chp_hourly_heat_rate_list = []
        chp_heat_rate_min = (sizing.electrical_output_to_thermal_output(chp_min_output)).to(ureg.Btu / ureg.hour)
        chp_heat_rate_cap = sizing.electrical_output_to_thermal_output(chp_size).to(ureg.Btu / ureg.hour)

        # TES sizing does not require electrical demand argument if operation mode is TLF
        tes_size = sizing.size_tes(chp_size=chp_size, load_following_type="TLF", class_dict=class_dict)

        tes_heat_rate_list_btu_hour = []
        soc_list = []

        for i, dem in enumerate(class_dict['demand'].hl):
            # Verifies acceptable input value range
            assert dem.magnitude >= 0
            if i == 0:
                current_status = class_dict['tes'].start * tes_size

            if chp_heat_rate_min <= dem <= chp_heat_rate_cap and tes_size == current_status:
                # If TES is full and chp meets demand, follow thermal load
                gen = dem.to(ureg.Btu / ureg.hour)
                chp_hourly_heat_rate_list.append(gen)
                stored_heat = Q_(0, ureg.Btu / ureg.hour)
                tes_heat_rate_list_btu_hour.append(stored_heat)
                new_status = (stored_heat * Q_(1, ureg.hour)) + current_status
                soc_list.append(new_status / tes_size)
                current_status = new_status
            elif chp_heat_rate_min <= dem <= chp_heat_rate_cap and current_status < tes_size:
                # If TES needs heat and chp meets demand, run CHP at full power and put excess in TES
                gen = chp_heat_rate_cap
                chp_hourly_heat_rate_list.append(gen)
                # Make sure SOC does not exceed 1 when heat is added
                soc_check = ((current_status / Q_(1, ureg.hours)) + gen - dem) / (tes_size / Q_(1, ureg.hours))
                if soc_check.magnitude < 1:
                    stored_heat = gen - dem
                    assert stored_heat >= 0
                else:
                    stored_heat = (tes_size - current_status) / Q_(1, ureg.hours)
                    assert stored_heat >= 0
                tes_heat_rate_list_btu_hour.append(stored_heat)
                new_status = (stored_heat * Q_(1, ureg.hours)) + current_status
                soc_list.append(new_status / tes_size)
                current_status = new_status
            elif dem < chp_heat_rate_min and dem <= (current_status / Q_(1, ureg.hours)):
                # If TES not empty, then let out heat to meet demand
                gen = Q_(0, ureg.Btu / ureg.hour)
                chp_hourly_heat_rate_list.append(gen)
                discharged_heat = gen - dem     # Should be negative
                assert discharged_heat <= 0
                tes_heat_rate_list_btu_hour.append(discharged_heat)
                new_status = (discharged_heat * Q_(1, ureg.hours)) + current_status
                soc_list.append(new_status / tes_size)
                current_status = new_status
            elif dem < chp_heat_rate_min and (current_status / Q_(1, ureg.hours)) < dem:
                # If TES is empty (or does not have enough to meet demand), then run CHP at full power
                gen = chp_heat_rate_cap
                chp_hourly_heat_rate_list.append(gen)

                soc_check = ((current_status / Q_(1, ureg.hours)) + gen - dem) / (tes_size / Q_(1, ureg.hours))
                if soc_check >= 1:
                    stored_heat = (tes_size - current_status) / Q_(1, ureg.hours)
                    assert stored_heat >= 0
                else:
                    stored_heat = gen - dem
                    assert stored_heat >= 0

                new_status = (stored_heat * Q_(1, ureg.hour)) + current_status
                tes_heat_rate_list_btu_hour.append(stored_heat)
                soc_list.append(new_status / tes_size)
                current_status = new_status
            elif chp_heat_rate_cap < dem and dem < (current_status / Q_(1, ureg.hours)):
                # If demand exceeds CHP generation, use TES
                gen = chp_heat_rate_cap
                chp_hourly_heat_rate_list.append(gen)

                soc_check = ((current_status / Q_(1, ureg.hours)) + gen - dem) / (tes_size / Q_(1, ureg.hours))
                if soc_check <= 0:
                    discharged_heat = -1 * current_status / Q_(1, ureg.hours)
                    assert discharged_heat <= 0
                else:
                    discharged_heat = gen - dem     # Should be negative
                    assert discharged_heat <= 0

                tes_heat_rate_list_btu_hour.append(discharged_heat)
                new_status = (discharged_heat * Q_(1, ureg.hour)) + current_status
                soc_list.append(new_status / tes_size)
                current_status = new_status
            elif chp_heat_rate_cap < dem and (current_status / Q_(1, ureg.hours)) < dem:
                # Discharge everything from TES
                gen = chp_heat_rate_cap
                chp_hourly_heat_rate_list.append(gen)
                discharged_heat = -1 * current_status / Q_(1, ureg.hours)  # Should be negative
                assert discharged_heat <= 0
                tes_heat_rate_list_btu_hour.append(discharged_heat)
                new_status = (discharged_heat * Q_(1, ureg.hours)) + current_status
                soc_list.append(new_status / tes_size)
                current_status = new_status
            else:
                raise Exception("Error in TLF calc_utility_electricity_needed function")

        return chp_hourly_heat_rate_list, tes_heat_rate_list_btu_hour, soc_list


def tlf_calc_electricity_generated(chp_gen_hourly_btuh=None, class_dict=None):
    """
    Updated 9/29/2022

    Calculates the electricity generated by the CHP system and the electricity bought
    from the local utility to make up the difference.

    For hourly heat generated by CHP, this function calculates the associated electrical
    output and compares this with the hourly electrical demand for the building. If
    demand is above the generated electricity,
    it calculates how much electricity needs to be purchased from the utility for that
    hour. Also calculates electricity generated by the CHP unit each hour.

    Used in the calc_avg_efficiency, calc_annual_fuel_use_and_costs, and
    calc_annual_electric_cost functions

    Parameters
    ----------
    ab: AuxBoiler Class
        contains initialized class data using CLI inputs (see command_line.py)
    chp: CHP Class
        contains initialized class data using CLI inputs (see command_line.py)
    demand: EnergyDemand Class
        contains initialized class data using CLI inputs (see command_line.py)

    Returns
    -------
    hourly_electricity_bought: list
        contains Quantity float values for electricity bought each hour in units of kWh
    hourly_electricity_gen: list
        contains Quantity float values for CHP electricity generated each hour in
        units of kWh
    """
    args_list = [chp_gen_hourly_btuh, class_dict]
    if any(elem is None for elem in args_list) is False:
        hourly_electricity_gen = []

        for i, hourly_heat_rate in enumerate(chp_gen_hourly_btuh):
            heat_gen_kw = hourly_heat_rate.to(ureg.kW)
            electric_gen_kwh = (sizing.thermal_output_to_electrical_output(heat_gen_kw) * Q_(1, ureg.hour)).to(ureg.kWh)
            hourly_electricity_gen.append(electric_gen_kwh)

        return hourly_electricity_gen
