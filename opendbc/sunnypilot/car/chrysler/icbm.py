"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""

from opendbc.car import structs
from opendbc.car.can_definitions import CanData
from opendbc.car.chrysler import chryslercan
from opendbc.car.chrysler.values import RAM_CARS
from opendbc.sunnypilot.car.chrysler.values_ext import ChryslerFlagsSP, ChryslerSafetyFlagsSP
from opendbc.sunnypilot.car.intelligent_cruise_button_management_interface_base import IntelligentCruiseButtonManagementInterfaceBase

ButtonType = structs.CarState.ButtonEvent.Type
SendButtonState = structs.IntelligentCruiseButtonManagement.SendButtonState


class IntelligentCruiseButtonManagementInterface(IntelligentCruiseButtonManagementInterfaceBase):
  def __init__(self, CP, CP_SP):
    super().__init__(CP, CP_SP)

  def update(self, CS, CC_SP, packer, frame, last_button_frame) -> list[CanData]:
    can_sends = []
    self.CC_SP = CC_SP
    self.ICBM = CC_SP.intelligentCruiseButtonManagement
    self.frame = frame
    self.last_button_frame = last_button_frame
    ram_cars = self.CP.carFingerprint in RAM_CARS
    das_bus = 2 if self.CP.carFingerprint in RAM_CARS else 0

    accel = self.ICBM.sendButton == SendButtonState.increase
    decel = self.ICBM.sendButton == SendButtonState.decrease

    # suspi: jvePilot Auto Follow (distance buttons, only with ACC engaged) and ACC Ready on Start (ACC_OnOff in the
    # first 5 s, every 5th frame, until ACC is ready), sent in the same message as ICBM's press, as jvePilot did.
    jve = CC_SP.jvePilot
    jve_buttons = bool(self.CP_SP.safetyParam & ChryslerSafetyFlagsSP.JVEPILOT_BUTTONS)  # what the panda will accept
    distance_inc = distance_dec = acc_on_off = False
    if jve_buttons and jve.enabled and CS.out.cruiseState.enabled and 0 <= jve.desiredFollowBars != CS.follow_bars:
      distance_inc = jve.desiredFollowBars > CS.follow_bars
      distance_dec = not distance_inc
    if jve_buttons and self.CP_SP.flags & ChryslerFlagsSP.JVEPILOT_ACC_READY_ON_START and frame < 500 and frame % 5 == 0 \
       and not CS.out.cruiseState.available:
      acc_on_off = True

    if accel or decel or distance_inc or distance_dec or acc_on_off:
      buttons = dict(accel=accel, decel=decel, distance_inc=distance_inc, distance_dec=distance_dec, acc_on_off=acc_on_off)

      if CS.button_counter != self.last_button_frame:
        self.last_button_frame = CS.button_counter

        if ram_cars:
          can_sends.append(chryslercan.create_cruise_buttons(packer, CS.cruise_btns, CS.button_counter, das_bus, **buttons))
        else:
          self.button_frame += 1
          button_counter_offset = [1, 1, 0, None][self.button_frame % 4]
          if button_counter_offset is not None:
            can_sends.append(chryslercan.create_cruise_buttons(packer, CS.cruise_btns, CS.button_counter + button_counter_offset, das_bus,
                                                               **buttons))

    return can_sends
