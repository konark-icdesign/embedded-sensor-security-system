#pragma once
#include <stdint.h>
#include <stddef.h>
#include <math.h>
#include <string.h>

namespace security {
inline uint32_t elapsed(uint32_t now, uint32_t then) { return now - then; }

struct Output {
    bool pir = false, radar = false, near = false, range_fault = true;
    bool degraded = true, alarm = false;
    bool investigating = false;
    bool fallback_alarm = false;
    float metres = NAN;
};

class Core {
    float ranges_[5] = {};
    uint8_t used_ = 0, cursor_ = 0, p_ = 0, m_ = 0, u_ = 0, agree_ = 0;
    uint8_t invalid_range_ = 0;
    uint32_t transport_heartbeat_ = 0, health_heartbeat_ = 0, last_tick_ = 0;
    bool transport_seen_ = false, health_seen_ = false, sampled_ = false, latch_ = false;
    bool investigating_ = false;
    bool fallback_latch_ = false;
    bool identity_requested_ = false;

  public:
    // HB only proves that a transport/process is alive. It must not suppress
    // local fallback by itself.
    void heartbeat(uint32_t now) {
        transport_heartbeat_ = now;
        transport_seen_ = true;
    }

    // HEALTH is reserved for a host pipeline that has checked the acquisition
    // path and is still processing fresh sensor/audio/video data.
    void hostHealth(uint32_t now) {
        heartbeat(now);
        health_heartbeat_ = now;
        health_seen_ = true;
    }

    void hostUnhealthy(uint32_t now) {
        heartbeat(now);
        health_seen_ = false;
    }

    void serverAlarm() { latch_ = true; }

    bool takeIdentityRequest() {
        const bool requested = identity_requested_;
        identity_requested_ = false;
        return requested;
    }

    void reset() {
        latch_ = false;
        fallback_latch_ = false;
        agree_ = 0;
    }

    bool command(const char *line, uint32_t now) {
        if (strcmp(line, "HB") == 0) {
            heartbeat(now);
            return true;
        }
        if (strcmp(line, "HEALTH") == 0) {
            hostHealth(now);
            return true;
        }
        if (strcmp(line, "UNHEALTHY") == 0) {
            hostUnhealthy(now);
            return true;
        }
        if (strcmp(line, "ALARM") == 0) {
            serverAlarm();
            return true;
        }
        if (strcmp(line, "ID") == 0) {
            identity_requested_ = true;
            return true;
        }
        if (strcmp(line, "YELLOW") == 0 || strcmp(line, "GREEN") == 0) {
            investigating_ = strcmp(line, "YELLOW") == 0;
            return true;
        }
        // Alarm reset requires a physical reset button; no unauthenticated remote reset.
        return false;
    }

    Output tick(uint32_t now, bool p, bool m, float distance, bool armed = true) {
        if (sampled_ && elapsed(now, last_tick_) > 250U) {
            used_ = 0;
            cursor_ = 0;
            p_ = 0;
            m_ = 0;
            u_ = 0;
            agree_ = 0;
            invalid_range_ = 0;
        }
        sampled_ = true;
        last_tick_ = now;

        p_ = p ? static_cast<uint8_t>(p_ < 3U ? p_ + 1U : 3U) : 0U;
        m_ = m ? static_cast<uint8_t>(m_ < 3U ? m_ + 1U : 3U) : 0U;

        Output o;
        o.pir = p_ >= 3U;
        o.radar = m_ >= 3U;

        const bool invalid =
            !isfinite(distance) || distance < .02F || distance > 4.F;
        o.range_fault = invalid;

        if (invalid) {
            // A single missed echo is common enough that it should not erase
            // the entire range history. Three consecutive invalid samples
            // make the range channel stale and clear its persistence.
            invalid_range_ = static_cast<uint8_t>(
                invalid_range_ < 3U ? invalid_range_ + 1U : 3U);
            if (invalid_range_ >= 3U) {
                used_ = 0;
                cursor_ = 0;
                u_ = 0;
            }
            o.near = u_ >= 3U;
        } else {
            invalid_range_ = 0;
            ranges_[cursor_] = distance;
            cursor_ = static_cast<uint8_t>((cursor_ + 1U) % 5U);
            if (used_ < 5U) {
                ++used_;
            }

            float a[5] = {};
            for (uint8_t i = 0; i < used_; ++i) {
                a[i] = ranges_[i];
            }
            for (uint8_t i = 1; i < used_; ++i) {
                const float value = a[i];
                uint8_t j = i;
                while (j > 0U && a[j - 1U] > value) {
                    a[j] = a[j - 1U];
                    --j;
                }
                a[j] = value;
            }

            o.metres = a[used_ / 2U];
            const bool near = used_ == 5U && o.metres < 1.8F;
            u_ = near ? static_cast<uint8_t>(u_ < 3U ? u_ + 1U : 3U) : 0U;
            o.near = u_ >= 3U;
        }

        // Only a recent HEALTH message suppresses autonomous fallback.
        // Repeated transport-only HB messages cannot keep the board "healthy".
        o.degraded = !health_seen_ || elapsed(now, health_heartbeat_) > 2000U;

        const bool fallback = armed && o.degraded && o.pir && o.radar && o.near;
        agree_ = fallback
                     ? static_cast<uint8_t>(agree_ < 10U ? agree_ + 1U : 10U)
                     : 0U;
        if (agree_ >= 10U) {
            latch_ = true;
            fallback_latch_ = true;
        }

        o.alarm = armed && latch_;
        o.investigating = investigating_ && !o.degraded;
        o.fallback_alarm = armed && fallback_latch_;
        return o;
    }
};

// Bounded serial line collector. Discard an entire oversized line, not its tail.
class LineBuffer {
    char data_[32] = {};
    size_t n_ = 0;
    bool overflow_ = false;

  public:
    bool feed(char c, Core &core, uint32_t now) {
        if (c == '\r') {
            return false;
        }
        if (c == '\n') {
            bool accepted = false;
            if (!overflow_) {
                data_[n_] = '\0';
                accepted = core.command(data_, now);
            }
            n_ = 0;
            overflow_ = false;
            return accepted;
        }
        if (overflow_) {
            return false;
        }
        if (n_ + 1U >= sizeof(data_)) {
            overflow_ = true;
            return false;
        }
        data_[n_++] = c;
        return false;
    }
};
} // namespace security
