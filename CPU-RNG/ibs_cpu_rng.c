/* Windows x86-64 CPUID-verified CPU RDSEED/RDRAND provider. Built with MSVC.
 * This is a direct instruction provider, not a claim of mathematically perfect randomness.
 * mode 1: RDSEED (conditioned hardware entropy), mode 2: RDRAND (hardware DRBG).
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <intrin.h>
#include <stdint.h>

__declspec(dllexport) int ibs_cpu_rng_supported(int mode) {
    int cpu[4] = {0,0,0,0};
    __cpuid(cpu, 0);
    if (mode == 1) {
        if (cpu[0] < 7) return 0;
        __cpuidex(cpu, 7, 0);
        return (cpu[1] & (1 << 18)) ? 1 : 0; /* RDSEED */
    }
    if (mode == 2) {
        if (cpu[0] < 1) return 0;
        __cpuid(cpu, 1);
        return (cpu[2] & (1 << 30)) ? 1 : 0; /* RDRAND */
    }
    return 0;
}

__declspec(dllexport) int ibs_cpu_rng_byte(int mode, unsigned char *out) {
    unsigned int value = 0;
    int i;
    if (!out || !ibs_cpu_rng_supported(mode)) return 0;
    for (i=0; i<4096; ++i) {
        int ok = (mode == 1) ? _rdseed32_step(&value) : _rdrand32_step(&value);
        if (ok) {
            *out = (unsigned char)(value & 0xffU);
            SecureZeroMemory(&value, sizeof(value));
            return 1;
        }
        YieldProcessor();
    }
    SecureZeroMemory(&value, sizeof(value));
    return 0;
}
