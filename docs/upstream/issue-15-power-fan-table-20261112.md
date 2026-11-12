I read how the firmware uses this table in the three public releases (1.6.0 `10f2f69`, 2.0.0 `93cb12f`, 2.1.0 `7ac453b`). `heater_fan.py`, `fan.py` and the two rows are the same in all three. I do not have a U1 here, so this is from the source, plus a test that feeds the shipped rows to the firmware's own `PrinterHeaterFan.callback`.

**What the five columns are**

`temp_speed_table` is a Snapmaker addition: it is not in mainline Klipper and not in `docs/`. In `klippy/extras/heater_fan.py` (lines 128 to 142) a row is

```
temp_threshold, target_temp_threshold, satisfied_heater_threshold, heater_count_threshold, rule_speed
```

Once a second, for each row from the top, the code counts the heads whose measured temperature is above column 1 or whose target is above column 2 ("satisfied"), and the heads with any target above 0 ("on"). If satisfied >= column 3 and on >= column 4, the fan is set to column 5 and the rows below are skipped. If no row matches, the fan is off.

So columns 3 and 4 are numbers of heads, not speeds, and column 1 is not the top of a temperature band. With 9999 there the measured temperature is ignored and only the targets count.

**What the shipped table does**

```
9999, 260, 1, 3, 1      # three or more heads on, at least one set above 260  -> 100 %
9999, 45, 1, 1, 0.6     # at least one head set above 45                      -> 60 %
```

| Heads | Shipped | First table proposed above | "Quieter" table proposed above |
|---|---|---|---|
| all off, cold | 0 % | 0 % | 0 % |
| all off, one nozzle still at 200 | 0 % | 0 % | 0 % |
| 1 head heating to 30 | 0 % | 60 % | 20 % |
| 1 head at 220 | 60 % | 60 % | 20 % |
| 1 head at 300 | 60 % | 60 % | 20 % |
| 2 heads, one at 300 | 60 % | 60 % | 20 % |
| 3 heads at 220 | 60 % | 60 % | 20 % |
| 3 heads, one at 270 | 100 % | 60 % | 20 % |
| 4 heads at 300 | 100 % | 60 % | 20 % |

These are the values the firmware code returns for each case: https://github.com/DesignMaster-Solutions/u1-fixpack/blob/main/tests/test_power_fan_table.py (`python3 tests/test_power_fan_table.py` prints the table).

So the stock table does not ask for 100 % on a normal print: it asks for 60 % while any head is set above 45, and 100 % only with three or more heads on and one of them above 260. It also stops the fan as soon as every target is 0, even with a hot nozzle.

**The two tables proposed above**

Read with the real columns, their first row (`260, 45, 0, 0.6, 0.6`) needs 0 satisfied heads and 0.6 heads on, so it matches as soon as any head has a target, and the second row is never reached. The first table is 60 % in every case, the quieter one is 20 % in every case, including four heads at 300 where stock gives 100 %. That is less PSU cooling than stock, so I would not copy the quieter one as it is.

In this format, "60 % from 45, 100 % above 260" would be written like this (it only shows the format, I am not suggesting speeds, since only Snapmaker knows how much air that PSU needs):

```
9999, 260, 1, 1, 1
9999, 45, 1, 1, 0.6
```

**cycle_time**

The section sets none, so `fan.py` uses its default of 0.010 s, which is 100 Hz software PWM. `cycle_time: 0.1` makes it 10 Hz, ten times slower, in case the intent was the opposite.

**If the fan really is at full speed**

@beyondthemind91an the table asks for 60 % duty on a one-head print. What does `heater_fan power_fan` show as speed in Fluidd or Mainsail while one head prints PLA? If it shows 0.6 and the fan still sounds flat out, the cause is in how that fan reacts to PWM on `!PC9`, not in the table. If it shows 1.0, something else is driving it and I would like to see the klippy.log.

If the maintainers want it, I can send a small pull request that documents the five columns in a comment above the table in `lava/printer.cfg`.
