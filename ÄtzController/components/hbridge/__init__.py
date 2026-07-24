import esphome.codegen as cg
import esphome.config_validation as cv
from esphome import pins
from esphome.const import CONF_ID

DEPENDENCIES = ["esp32"]

hbridge_ns = cg.esphome_ns.namespace("hbridge")
HBridgeController = hbridge_ns.class_("HBridgeController", cg.Component)

CONF_A_HIGH_SIDE_PIN = "a_high_side_pin"
CONF_A_LOW_SIDE_PIN = "a_low_side_pin"
CONF_B_HIGH_SIDE_PIN = "b_high_side_pin"
CONF_B_LOW_SIDE_PIN = "b_low_side_pin"

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(HBridgeController),
        cv.Required(CONF_A_HIGH_SIDE_PIN): pins.gpio_output_pin_schema,
        cv.Required(CONF_A_LOW_SIDE_PIN): pins.gpio_output_pin_schema,
        cv.Required(CONF_B_HIGH_SIDE_PIN): pins.gpio_output_pin_schema,
        cv.Required(CONF_B_LOW_SIDE_PIN): pins.gpio_output_pin_schema,
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config):
    pins_to_create = [
        await cg.gpio_pin_expression(config[CONF_A_HIGH_SIDE_PIN]),
        await cg.gpio_pin_expression(config[CONF_A_LOW_SIDE_PIN]),
        await cg.gpio_pin_expression(config[CONF_B_HIGH_SIDE_PIN]),
        await cg.gpio_pin_expression(config[CONF_B_LOW_SIDE_PIN]),
    ]
    var = cg.new_Pvariable(config[CONF_ID], *pins_to_create)
    await cg.register_component(var, config)
