from __future__ import (
    unicode_literals,
    absolute_import,
    print_function,
    division,
    )
str = type('')


import sys
import pytest
import warnings
from time import sleep
from threading import Event
from functools import partial

import mock

from gpiozero.pins.mock import MockChargingPin, MockTriggerPin
from gpiozero.threads import GPIOThread
from gpiozero import *



def test_input_initial_values(mock_factory):
    pin = mock_factory.pin(4)
    with InputDevice(4, pull_up=True) as device:
        assert pin.function == 'input'
        assert pin.pull == 'up'
        assert device.pull_up
    with InputDevice(4, pull_up=False) as device:
        assert pin.pull == 'down'
        assert not device.pull_up

def test_input_is_active_low(mock_factory):
    pin = mock_factory.pin(2)
    with InputDevice(2, pull_up=True) as device:
        pin.drive_high()
        assert not device.is_active
        assert repr(device) == '<gpiozero.InputDevice object on pin GPIO2, pull_up=True, is_active=False>'
        pin.drive_low()
        assert device.is_active
        assert repr(device) == '<gpiozero.InputDevice object on pin GPIO2, pull_up=True, is_active=True>'

def test_input_is_active_high(mock_factory):
    pin = mock_factory.pin(4)
    with InputDevice(4, pull_up=False) as device:
        pin.drive_high()
        assert device.is_active
        assert repr(device) == '<gpiozero.InputDevice object on pin GPIO4, pull_up=False, is_active=True>'
        pin.drive_low()
        assert not device.is_active
        assert repr(device) == '<gpiozero.InputDevice object on pin GPIO4, pull_up=False, is_active=False>'

def test_input_pulled_up(mock_factory):
    pin = mock_factory.pin(2)
    with pytest.raises(PinFixedPull):
        InputDevice(2, pull_up=False)

def test_input_event_activated(mock_factory):
    event = Event()
    pin = mock_factory.pin(4)
    with DigitalInputDevice(4) as device:
        device.when_activated = lambda: event.set()
        assert not event.is_set()
        pin.drive_high()
        assert event.is_set()

def test_input_event_deactivated(mock_factory):
    event = Event()
    pin = mock_factory.pin(4)
    with DigitalInputDevice(4) as device:
        device.when_deactivated = lambda: event.set()
        assert not event.is_set()
        pin.drive_high()
        assert not event.is_set()
        pin.drive_low()
        assert event.is_set()

def test_input_partial_callback(mock_factory):
    event = Event()
    pin = mock_factory.pin(4)
    def foo(a, b):
        event.set()
        return a + b
    bar = partial(foo, 1)
    baz = partial(bar, 2)
    with DigitalInputDevice(4) as device:
        device.when_activated = baz
        assert not event.is_set()
        pin.drive_high()
        assert event.is_set()

def test_input_wait_active(mock_factory):
    pin = mock_factory.pin(4)
    with DigitalInputDevice(4) as device:
        pin.drive_high()
        assert device.wait_for_active(1)
        assert not device.wait_for_inactive(0)

def test_input_wait_inactive(mock_factory):
    pin = mock_factory.pin(4)
    with DigitalInputDevice(4) as device:
        assert device.wait_for_inactive(1)
        assert not device.wait_for_active(0)

def test_input_init_fail(mock_factory):
    with pytest.raises(ValueError):
        DigitalInputDevice(4, bounce_time='foo')
    with pytest.raises(ValueError):
        SmoothedInputDevice(4, threshold='foo')
    with mock.patch('gpiozero.threads.GPIOThread.start') as start:
        start.side_effect = RuntimeError('failed to start thread')
        with pytest.raises(RuntimeError):
            LineSensor(4)
        with pytest.raises(RuntimeError):
            MotionSensor(4)
        with pytest.raises(RuntimeError):
            LightSensor(4)
        with pytest.raises(RuntimeError):
            DistanceSensor(4, 5)

def test_input_smoothed_attrib(mock_factory):
    pin = mock_factory.pin(4)
    with SmoothedInputDevice(4, threshold=0.5, queue_len=5, partial=False) as device:
        assert repr(device) == '<gpiozero.SmoothedInputDevice object on pin GPIO4, pull_up=False>'
        assert device.threshold == 0.5
        assert device.queue_len == 5
        assert not device.partial
        device._queue.start()
        assert not device.is_active
        with pytest.raises(InputDeviceError):
            device.threshold = 1
    with pytest.raises(BadQueueLen):
        SmoothedInputDevice(4, queue_len=-1)
    with pytest.raises(BadWaitTime):
        SmoothedInputDevice(4, sample_wait=-1)

def test_input_smoothed_values(mock_factory):
    pin = mock_factory.pin(4)
    with SmoothedInputDevice(4) as device:
        device._queue.start()
        assert not device.is_active
        pin.drive_high()
        assert device.wait_for_active(1)
        pin.drive_low()
        assert device.wait_for_inactive(1)

def test_input_button(mock_factory):
    pin = mock_factory.pin(2)
    with Button(2) as button:
        assert pin.pull == 'up'
        assert not button.is_pressed
        pin.drive_low()
        assert button.is_pressed
        assert button.wait_for_press(1)
        pin.drive_high()
        assert not button.is_pressed
        assert button.wait_for_release(1)

def test_input_button_hold(mock_factory):
    pin = mock_factory.pin(2)
    evt = Event()
    evt2 = Event()
    with Button(2) as button:
        with pytest.raises(ValueError):
            button.hold_time = -1
        button.hold_time = 0.1
        assert button.hold_time == 0.1
        assert not button.hold_repeat
        assert button.when_held is None
        button.when_held = evt.set
        assert button.when_held is not None
        pin.drive_low()
        assert evt.wait(1)
        assert button.is_held
        assert button.held_time >= 0.0
        pin.drive_high()
        evt.clear()
        assert button.held_time is None
        assert not button.is_held
        button.hold_repeat = True
        pin.drive_low()
        assert evt.wait(1)
        evt.clear()
        assert evt.wait(1)
        pin.drive_high()
        evt.clear()
        assert not evt.wait(0.1)

def test_input_line_sensor(mock_factory):
    pin = mock_factory.pin(4)
    with LineSensor(4) as sensor:
        pin.drive_low() # logic is inverted for line sensor
        assert sensor.wait_for_line(1)
        assert sensor.line_detected
        pin.drive_high()
        assert sensor.wait_for_no_line(1)
        assert not sensor.line_detected

def test_input_motion_sensor(mock_factory):
    pin = mock_factory.pin(4)
    with MotionSensor(4) as sensor:
        pin.drive_high()
        assert sensor.wait_for_motion(1)
        assert sensor.motion_detected
        pin.drive_low()
        assert sensor.wait_for_no_motion(1)
        assert not sensor.motion_detected

@pytest.mark.skipif(hasattr(sys, 'pypy_version_info'),
                    reason='timing is too random on pypy')
def test_input_light_sensor(mock_factory):
    pin = mock_factory.pin(4, pin_class=MockChargingPin)
    assert isinstance(pin, MockChargingPin)
    with LightSensor(4) as sensor:
        pin.charge_time = 0.1
        assert sensor.wait_for_dark(1)
        pin.charge_time = 0.0
        assert sensor.wait_for_light(1)

@pytest.mark.skipif(hasattr(sys, 'pypy_version_info'),
                    reason='timing is too random on pypy')
def test_input_distance_sensor(mock_factory):
    echo_pin = mock_factory.pin(4)
    trig_pin = mock_factory.pin(5, pin_class=MockTriggerPin,
                                echo_pin=echo_pin, echo_time=0.02)
    with pytest.raises(ValueError):
        DistanceSensor(4, 5, max_distance=-1)
    # normal queue len is large (because the sensor is *really* jittery) but
    # we want quick tests and we've got precisely controlled pins :)
    with DistanceSensor(4, 5, queue_len=5, max_distance=1) as sensor:
        assert sensor.max_distance == 1
        assert sensor.trigger is trig_pin
        assert sensor.echo is echo_pin
        assert sensor.wait_for_out_of_range(1)
        assert not sensor.in_range
        # should be waay before max-distance so this should work
        assert sensor.distance == 1.0
        trig_pin.echo_time = 0.0
        assert sensor.wait_for_in_range(1)
        assert sensor.in_range
        # depending on speed of machine, may not reach 0 here
        assert sensor.distance < sensor.threshold_distance
        sensor.threshold_distance = 0.1
        assert sensor.threshold_distance == 0.1
        with pytest.raises(ValueError):
            sensor.max_distance = -1
        sensor.max_distance = 20
        assert sensor.max_distance == 20
        assert sensor.threshold_distance == 0.1

def test_input_distance_sensor_edge_cases(mock_factory):
    echo_pin = mock_factory.pin(4)
    trig_pin = mock_factory.pin(5)  # note: normal pin
    with warnings.catch_warnings(record=True) as w:
        with DistanceSensor(4, 5, queue_len=5, max_distance=1, partial=True) as sensor:
            # Test we get a warning about the echo pin being set high
            echo_pin.drive_high()
            sleep(0.5)
            assert sensor.value == 0
            # Test we get a warning about receiving no echo
            echo_pin.drive_low()
            sleep(0.5)
        for rec in w:
            if str(rec.message) == 'echo pin set high':
                break
        else:
            assert False
        for rec in w:
            if str(rec.message) == 'no echo received':
                break
        else:
            assert False
