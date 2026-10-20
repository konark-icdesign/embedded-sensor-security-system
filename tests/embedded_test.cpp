#include "../firmware/night_security/core.h"
#include <assert.h>
#include <stdio.h>
#include <stdint.h>
#include <string>

int main() {
    using security::Core;
    {
        Core c;
        assert(c.command("YELLOW", 0));
        c.hostHealth(0);
        assert(c.tick(0, false, false, 3.F).investigating);
        assert(c.command("GREEN", 100));
        assert(!c.tick(100, false, false, 3.F).investigating);
        c.command("ALARM", 200);
        c.command("GREEN", 300);
        auto out = c.tick(300, false, false, 3.F);
        assert(out.alarm && !out.fallback_alarm);
        c.reset();
        for (uint32_t t = 400; t < 6000; t += 100) {
            out = c.tick(t, true, true, 1.2F);
        }
        assert(out.alarm && out.fallback_alarm);
        puts("PASS central state commands preserve alarm latch and fallback provenance");
    }
    {
        Core c;
        security::Output o;
        for (uint32_t t = 0; t < 2000; t += 100) {
            c.hostHealth(t);
            o = c.tick(t, false, false, t == 1000 ? .35F : 3.F);
            assert(!o.near);
            assert(!o.alarm);
        }
        puts("PASS isolated echo rejected");
    }
    {
        Core c;
        security::Output o;
        for (uint32_t t = 0; t < 2000; t += 100) {
            c.hostHealth(t);
            o = c.tick(t, false, false, 1.2F);
        }
        assert(o.near);
        assert(!o.alarm);

        o = c.tick(2000, false, false, NAN);
        assert(o.near && o.range_fault);
        o = c.tick(2100, false, false, NAN);
        assert(o.near && o.range_fault);
        o = c.tick(2200, false, false, NAN);
        assert(!o.near && o.range_fault);
        puts("PASS isolated ultrasonic dropouts are tolerated but persistent failure clears range evidence");
    }
    {
        Core c;
        security::Output o;
        for (uint32_t t = 0; t < 5000; t += 100) {
            o = c.tick(t, true, true, 1.2F);
        }
        assert(o.alarm && o.degraded);
        c.hostHealth(5000);
        o = c.tick(5000, false, false, 3.F);
        assert(o.alarm);
        c.reset();
        o = c.tick(5100, false, false, 3.F);
        assert(!o.alarm);
        puts("PASS offline fallback latches until explicit reset");
    }
    {
        Core c;
        security::Output o;
        for (uint32_t t = 0; t < 5000; t += 100) {
            c.hostHealth(t);
            o = c.tick(t, true, true, 1.2F);
            assert(!o.alarm);
        }
        c.serverAlarm();
        o = c.tick(5000, false, false, 3.F);
        assert(o.alarm);
        puts("PASS healthy host controls central alarm");
    }
    {
        Core c;
        c.hostHealth(UINT32_MAX - 1000U);
        auto o = c.tick(500, false, false, 3.F);
        assert(!o.degraded);
        o = c.tick(1500, false, false, 3.F);
        assert(o.degraded);
        puts("PASS health timeout survives millis wraparound");
    }
    {
        Core c;
        security::LineBuffer b;
        assert(!c.takeIdentityRequest());
        for (char x : std::string("ID\n")) {
            b.feed(x, c, 42);
        }
        assert(c.takeIdentityRequest());
        assert(!c.takeIdentityRequest());
        puts("PASS firmware identity request is bounded and one-shot");
    }
    {
        Core c;
        security::LineBuffer b;
        std::string bad(300, 'x');
        bad += "ALARM\n";
        for (char x : bad) {
            b.feed(x, c, 0);
        }
        assert(!c.tick(0, false, false, 3.F).alarm);
        for (char x : std::string("ALARM\n")) {
            b.feed(x, c, 100);
        }
        assert(c.tick(100, false, false, 3.F).alarm);
        puts("PASS bounded command parser rejects overflow tails");
    }
    {
        Core c;
        c.hostHealth(0);
        c.tick(0, true, true, .5F);
        c.tick(100, true, true, .6F);
        c.tick(200, true, true, .7F);
        auto o = c.tick(600, true, true, 3.5F);
        assert(!o.near && !o.alarm);
        assert(o.metres > 3.49F && o.metres < 3.51F);
        puts("PASS sample gap clears circular range history without stale samples");
    }
    {
        Core c;
        for (uint32_t t = 0; t < 5000; t += 100) {
            assert(!c.tick(t, true, true, 1.2F, false).alarm);
        }
        puts("PASS warm-up inhibits alarm");
    }
    {
        Core c;
        security::Output o;
        for (uint32_t n = 0; n < 300; ++n) {
            const float range = ((n + 1U) % 10U == 0U) ? NAN : 1.0F;
            o = c.tick(n * 100U, true, true, range, true);
        }
        assert(o.alarm && o.fallback_alarm);
        puts("PASS one missed ultrasonic echo per ten samples does not disable local fallback");
    }
    {
        Core c;
        c.hostHealth(0);
        security::Output o;
        for (uint32_t t = 0; t <= 4000; t += 100) {
            if (t != 0 && t % 500U == 0U) {
                c.heartbeat(t); // transport still alive, acquisition health is not refreshed
            }
            o = c.tick(t, true, true, 1.2F, true);
        }
        assert(o.degraded);
        assert(o.alarm && o.fallback_alarm);
        puts("PASS transport heartbeat cannot hide a dead host acquisition pipeline");
    }
    puts("ALL EMBEDDED HOST TESTS PASSED");
}
