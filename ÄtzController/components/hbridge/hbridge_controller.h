#pragma once

#include "esphome/core/component.h"
#include "esphome/core/gpio.h"
#include "driver/gpio.h"
#include "esp_timer.h"

namespace esphome {
namespace hbridge {

class HBridgeController : public Component {
 public:
  HBridgeController(gpio::GPIOPin *a_high_side, gpio::GPIOPin *a_low_side,
                    gpio::GPIOPin *b_high_side, gpio::GPIOPin *b_low_side)
      : a_high_side_(a_high_side),
        a_low_side_(a_low_side),
        b_high_side_(b_high_side),
        b_low_side_(b_low_side) {}

  void setup() override {
    this->a_high_side_->setup();
    this->a_low_side_->setup();
    this->b_high_side_->setup();
    this->b_low_side_->setup();
    this->all_off_();
    this->timer_ = esp_timer_create_args_t{
        .callback = &HBridgeController::timer_callback_,
        .arg = this,
        .dispatch_method = ESP_TIMER_TASK,
        .name = "hbridge",
        .skip_unhandled_events = false,
    };
    if (esp_timer_create(&this->timer_, &this->timer_handle_) != ESP_OK) {
      this->mark_failed();
    }
  }

  void loop() override {}

  void start(uint32_t reverse_us, uint32_t forward_us, uint32_t pause_us) {
    if (this->is_failed() || this->timer_handle_ == nullptr) return;
    this->reverse_us_ = this->clamp_us_(reverse_us);
    this->forward_us_ = this->clamp_us_(forward_us);
    this->pause_us_ = this->clamp_us_(pause_us);
    this->running_ = true;
    this->phase_ = Phase::REVERSE;
    this->apply_phase_();
    this->arm_(this->reverse_us_);
  }

  void stop() {
    this->running_ = false;
    if (this->timer_handle_ != nullptr) {
      esp_timer_stop(this->timer_handle_);
    }
    this->phase_ = Phase::OFF;
    this->all_off_();
  }

  float get_setup_priority() const override { return setup_priority::HARDWARE; }

 protected:
  enum class Phase : uint8_t {
    OFF,
    REVERSE,
    DEAD_AFTER_REVERSE,
    PAUSE_AFTER_REVERSE,
    FORWARD,
    DEAD_AFTER_FORWARD,
    PAUSE_AFTER_FORWARD,
  };

  static constexpr uint32_t MIN_US = 1;
  static constexpr uint32_t MAX_US = 1000;
  static constexpr uint32_t DEAD_TIME_US = 10;

  static void timer_callback_(void *arg) {
    static_cast<HBridgeController *>(arg)->advance_();
  }

  uint32_t clamp_us_(uint32_t value) const {
    return value < MIN_US ? MIN_US : (value > MAX_US ? MAX_US : value);
  }

  void arm_(uint32_t duration_us) {
    esp_timer_stop(this->timer_handle_);
    esp_timer_start_once(this->timer_handle_, duration_us);
  }

  void advance_() {
    if (!this->running_) return;
    switch (this->phase_) {
      case Phase::REVERSE:
        this->phase_ = Phase::DEAD_AFTER_REVERSE;
        this->all_off_();
        this->arm_(DEAD_TIME_US);
        break;
      case Phase::DEAD_AFTER_REVERSE:
        this->phase_ = Phase::PAUSE_AFTER_REVERSE;
        this->arm_(this->pause_us_);
        break;
      case Phase::PAUSE_AFTER_REVERSE:
        this->phase_ = Phase::FORWARD;
        this->apply_phase_();
        this->arm_(this->forward_us_);
        break;
      case Phase::FORWARD:
        this->phase_ = Phase::DEAD_AFTER_FORWARD;
        this->all_off_();
        this->arm_(DEAD_TIME_US);
        break;
      case Phase::DEAD_AFTER_FORWARD:
        this->phase_ = Phase::PAUSE_AFTER_FORWARD;
        this->arm_(this->pause_us_);
        break;
      case Phase::PAUSE_AFTER_FORWARD:
        this->phase_ = Phase::REVERSE;
        this->apply_phase_();
        this->arm_(this->reverse_us_);
        break;
      case Phase::OFF:
        break;
    }
  }

  void apply_phase_() {
    this->all_off_();
    if (this->phase_ == Phase::REVERSE) {
      this->b_high_side_->digital_write(true);
      this->a_low_side_->digital_write(true);
    } else if (this->phase_ == Phase::FORWARD) {
      this->a_high_side_->digital_write(true);
      this->b_low_side_->digital_write(true);
    }
  }

  void all_off_() {
    this->a_high_side_->digital_write(false);
    this->a_low_side_->digital_write(false);
    this->b_high_side_->digital_write(false);
    this->b_low_side_->digital_write(false);
  }

  gpio::GPIOPin *a_high_side_;
  gpio::GPIOPin *a_low_side_;
  gpio::GPIOPin *b_high_side_;
  gpio::GPIOPin *b_low_side_;
  esp_timer_handle_t timer_handle_{nullptr};
  esp_timer_create_args_t timer_{};
  Phase phase_{Phase::OFF};
  uint32_t reverse_us_{1};
  uint32_t forward_us_{1};
  uint32_t pause_us_{1};
  volatile bool running_{false};
};

}  // namespace hbridge
}  // namespace esphome
