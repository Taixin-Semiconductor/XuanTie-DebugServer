/* SPDX-License-Identifier: MIT
 * CK-Link inspection and explicitly requested loader configuration selection.
 * No interface claims, device resets, firmware payloads or target commands.
 */
#include <libusb.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static bool loader(const struct libusb_device_descriptor *d)
{
    return d->idVendor == 0xc510 && d->idProduct == 0xb211;
}

static bool normal(const struct libusb_device_descriptor *d)
{
    return d->idVendor == 0x32bf && d->idProduct == 0xb210;
}

static void usage(void)
{
    puts("cklink-usb --inspect | --activate [--serial SERIAL] | "
         "--require-single-normal [--serial SERIAL]\n"
         "Inspection is read-only. Activation selects configuration 1 once "
         "on an unconfigured c510:b211 loader; it changes USB state.");
}

int main(int argc, char **argv)
{
    if (argc == 2 && strcmp(argv[1], "--help") == 0) {
        usage();
        return 0;
    }
    if (argc != 2 && argc != 4) {
        usage();
        return 2;
    }
    const bool activate = strcmp(argv[1], "--activate") == 0;
    const bool require_normal = strcmp(argv[1], "--require-single-normal") == 0;
    const bool inspect = strcmp(argv[1], "--inspect") == 0;
    const char *wanted = NULL;
    if ((!activate && !require_normal && !inspect) ||
        (argc == 4 && (inspect || strcmp(argv[2], "--serial") != 0 || !argv[3][0]))) {
        usage();
        return 2;
    }
    if (argc == 4)
        wanted = argv[3];

    libusb_context *ctx = NULL;
    int rc = libusb_init(&ctx);
    if (rc != 0) {
        fprintf(stderr, "libusb_init: %s\n", libusb_error_name(rc));
        return 1;
    }
    libusb_device **devices = NULL;
    const ssize_t count = libusb_get_device_list(ctx, &devices);
    if (count < 0) {
        fprintf(stderr, "USB enumeration: %s\n", libusb_error_name((int)count));
        libusb_exit(ctx);
        return 1;
    }
    libusb_device *selected = NULL;
    unsigned loaders = 0, normals = 0, matches = 0;
    int result = 1;
    for (ssize_t i = 0; i < count; i++) {
        struct libusb_device_descriptor d;
        rc = libusb_get_device_descriptor(devices[i], &d);
        if (rc != 0) {
            fprintf(stderr, "Cannot inspect USB device descriptor: %s\n", libusb_error_name(rc));
            goto done;
        }
        if (!loader(&d) && !normal(&d))
            continue;
        if (loader(&d))
            loaders++;
        else
            normals++;
        libusb_device_handle *handle = NULL;
        rc = libusb_open(devices[i], &handle);
        if (rc != 0) {
            fprintf(stderr, "%04x:%04x at bus %u address %u cannot be opened: %s. "
                    "Allow the accessory in macOS and retry outside a process sandbox.\n",
                    d.idVendor, d.idProduct, libusb_get_bus_number(devices[i]),
                    libusb_get_device_address(devices[i]), libusb_error_name(rc));
            goto done;
        }
        unsigned char serial[256] = {0};
        const int length = d.iSerialNumber ?
            libusb_get_string_descriptor_ascii(handle, d.iSerialNumber, serial, sizeof(serial)-1) : -1;
        if (length > 0)
            serial[length] = '\0';
        int config = -1;
        rc = libusb_get_configuration(handle, &config);
        libusb_close(handle);
        if (rc != 0) {
            fprintf(stderr, "Cannot read %04x:%04x configuration: %s\n",
                    d.idVendor, d.idProduct, libusb_error_name(rc));
            goto done;
        }
        printf("%s %04x:%04x bus=%u address=%u configuration=%d serial=%s\n",
               loader(&d) ? "loader" : "normal", d.idVendor, d.idProduct,
               libusb_get_bus_number(devices[i]), libusb_get_device_address(devices[i]),
               config, length > 0 ? (char *)serial : "unavailable");
        if ((!wanted || (length > 0 && strcmp(wanted, (char *)serial) == 0)) &&
            ((activate && loader(&d)) || (require_normal && normal(&d)))) {
            selected = devices[i];
            matches++;
        }
    }
    if (inspect) {
        if (loaders + normals == 0)
            puts("No CK-Link loader or normal-mode probe is connected.");
        result = 0;
        goto done;
    }
    if (matches != 1 || (activate && !wanted && loaders != 1) ||
        (require_normal && (normals != 1 || loaders != 0))) {
        fputs("Refusing action: select exactly one matching loader for activation; "
              "target checks require exactly one normal-mode CK-Link and no loaders. "
              "Use --serial for activation or unplug other probes.\n", stderr);
        goto done;
    }
    libusb_device_handle *handle = NULL;
    rc = libusb_open(selected, &handle);
    if (rc != 0) {
        fprintf(stderr, "Selected probe cannot be opened: %s\n", libusb_error_name(rc));
        goto done;
    }
    int config = -1;
    rc = libusb_get_configuration(handle, &config);
    if (rc != 0) {
        fprintf(stderr, "Selected probe configuration: %s\n", libusb_error_name(rc));
    } else if (require_normal) {
        if (config == 1)
            result = 0;
        else
            fputs("Normal probe does not have configuration 1; no action taken.\n", stderr);
    } else if (config != 0) {
        fputs("Loader is already configured; refusing to repeat SET_CONFIGURATION.\n", stderr);
    } else {
        struct libusb_config_descriptor *descriptor = NULL;
        rc = libusb_get_config_descriptor_by_value(selected, 1, &descriptor);
        if (rc != 0) {
            fprintf(stderr, "Loader has no readable configuration 1: %s\n", libusb_error_name(rc));
        } else {
            libusb_free_config_descriptor(descriptor);
            puts("Selecting loader configuration 1 once (USB state change).");
            rc = libusb_set_configuration(handle, 1);
            if (rc != 0) {
                fprintf(stderr, "SET_CONFIGURATION(1): %s; no automatic retry.\n", libusb_error_name(rc));
            } else {
                puts("Wait for 32bf:b210, approve the macOS accessory prompt, then run debugserver list.");
                result = 0;
            }
        }
    }
    libusb_close(handle);
done:
    libusb_free_device_list(devices, 1);
    libusb_exit(ctx);
    return result;
}
