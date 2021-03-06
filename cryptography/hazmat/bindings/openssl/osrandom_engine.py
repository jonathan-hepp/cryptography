# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

INCLUDES = """
#ifdef _WIN32
#include <Wincrypt.h>
#else
#include <fcntl.h>
#include <unistd.h>
#endif
"""

TYPES = """
static const char *const Cryptography_osrandom_engine_name;
static const char *const Cryptography_osrandom_engine_id;
"""

FUNCTIONS = """
int Cryptography_add_osrandom_engine(void);
"""

MACROS = """
"""

WIN32_CUSTOMIZATIONS = """
static HCRYPTPROV hCryptProv = 0;

static int osrandom_init(ENGINE *e) {
    if (hCryptProv > 0) {
        return 1;
    }
    if (CryptAcquireContext(&hCryptProv, NULL, NULL,
                            PROV_RSA_FULL, CRYPT_VERIFYCONTEXT)) {
        return 1;
    } else {
        return 0;
    }
}

static int osrandom_rand_bytes(unsigned char *buffer, int size) {
    if (hCryptProv == 0) {
        return 0;
    }

    if (!CryptGenRandom(hCryptProv, (DWORD)size, buffer)) {
        ERR_put_error(
            ERR_LIB_RAND, 0, ERR_R_RAND_LIB, "osrandom_engine.py", 0
        );
        return 0;
    }
    return 1;
}

static int osrandom_finish(ENGINE *e) {
    if (CryptReleaseContext(hCryptProv, 0)) {
        hCryptProv = 0;
        return 1;
    } else {
        return 0;
    }
}

static int osrandom_rand_status(void) {
    if (hCryptProv == 0) {
        return 0;
    } else {
        return 1;
    }
}
"""

POSIX_CUSTOMIZATIONS = """
static int urandom_fd = -1;

static int osrandom_finish(ENGINE *e);

static int osrandom_init(ENGINE *e) {
    if (urandom_fd > -1) {
        return 1;
    }
    urandom_fd = open("/dev/urandom", O_RDONLY);
    if (urandom_fd > -1) {
        int flags = fcntl(urandom_fd, F_GETFD);
        if (flags == -1) {
            osrandom_finish(e);
            return 0;
        } else if (fcntl(urandom_fd, F_SETFD, flags | FD_CLOEXEC) == -1) {
            osrandom_finish(e);
            return 0;
        }
        return 1;
    } else {
        return 0;
    }
}

static int osrandom_rand_bytes(unsigned char *buffer, int size) {
    ssize_t n;
    while (size > 0) {
        do {
            n = read(urandom_fd, buffer, (size_t)size);
        } while (n < 0 && errno == EINTR);
        if (n <= 0) {
            ERR_put_error(
                ERR_LIB_RAND, 0, ERR_R_RAND_LIB, "osrandom_engine.py", 0
            );
            return 0;
        }
        buffer += n;
        size -= n;
    }
    return 1;
}

static int osrandom_finish(ENGINE *e) {
    int n;
    do {
        n = close(urandom_fd);
    } while (n < 0 && errno == EINTR);
    urandom_fd = -1;
    if (n < 0) {
        return 0;
    } else {
        return 1;
    }
}

static int osrandom_rand_status(void) {
    if (urandom_fd == -1) {
        return 0;
    } else {
        return 1;
    }
}
"""

CUSTOMIZATIONS = """
static const char *Cryptography_osrandom_engine_id = "osrandom";
static const char *Cryptography_osrandom_engine_name = "osrandom_engine";

#if defined(_WIN32)
%(WIN32_CUSTOMIZATIONS)s
#else
%(POSIX_CUSTOMIZATIONS)s
#endif

/* This replicates the behavior of the OpenSSL FIPS RNG, which returns a
   -1 in the event that there is an error when calling RAND_pseudo_bytes. */
static int osrandom_pseudo_rand_bytes(unsigned char *buffer, int size) {
    int res = osrandom_rand_bytes(buffer, size);
    if (res == 0) {
        return -1;
    } else {
        return res;
    }
}

static RAND_METHOD osrandom_rand = {
    NULL,
    osrandom_rand_bytes,
    NULL,
    NULL,
    osrandom_pseudo_rand_bytes,
    osrandom_rand_status,
};

int Cryptography_add_osrandom_engine(void) {
    ENGINE *e = ENGINE_new();
    if (e == NULL) {
        return 0;
    }
    if(!ENGINE_set_id(e, Cryptography_osrandom_engine_id) ||
            !ENGINE_set_name(e, Cryptography_osrandom_engine_name) ||
            !ENGINE_set_RAND(e, &osrandom_rand) ||
            !ENGINE_set_init_function(e, osrandom_init) ||
            !ENGINE_set_finish_function(e, osrandom_finish)) {
        ENGINE_free(e);
        return 0;
    }
    if (!ENGINE_add(e)) {
        ENGINE_free(e);
        return 0;
    }
    if (!ENGINE_free(e)) {
        return 0;
    }

    return 1;
}
""" % {
    "WIN32_CUSTOMIZATIONS": WIN32_CUSTOMIZATIONS,
    "POSIX_CUSTOMIZATIONS": POSIX_CUSTOMIZATIONS,
}

CONDITIONAL_NAMES = {}
