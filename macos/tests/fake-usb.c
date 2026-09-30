/* Unit-test libusb seam. Never links a real USB library. */
#include <libusb.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
struct libusb_device { int index; };
struct libusb_device_handle { libusb_device *device; };
static struct libusb_device devs[2] = {{0}, {1}};
static struct libusb_device_handle handles[2];
static libusb_device *list[3];
static const char *scenario;
int libusb_init(libusb_context **ctx) { *ctx = NULL; scenario = getenv("USB_TEST_SCENARIO"); return 0; }
void libusb_exit(libusb_context *ctx) { (void)ctx; }
ssize_t libusb_get_device_list(libusb_context *ctx, libusb_device ***out)
{
    (void)ctx;
    const int n = strstr(scenario, "two") ? 2 : strcmp(scenario, "absent") == 0 ? 0 : 1;
    list[0] = n ? &devs[0] : NULL;
    list[1] = n == 2 ? &devs[1] : NULL;
    list[2] = NULL;
    *out = list;
    return n;
}
void libusb_free_device_list(libusb_device **devices, int refs) { (void)devices; (void)refs; }
int libusb_get_device_descriptor(libusb_device *dev, struct libusb_device_descriptor *d)
{
    memset(d, 0, sizeof(*d));
    const int normal = strstr(scenario, "normal") != NULL &&
        (strcmp(scenario, "normal-two-mixed") != 0 || dev->index == 0);
    d->idVendor = normal ? 0x32bf : 0xc510;
    d->idProduct = normal ? 0xb210 : 0xb211;
    d->iSerialNumber = 1;
    return 0;
}
uint8_t libusb_get_bus_number(libusb_device *dev) { (void)dev; return 1; }
uint8_t libusb_get_device_address(libusb_device *dev) { return (uint8_t)(dev->index+1); }
int libusb_open(libusb_device *dev, libusb_device_handle **h)
{
    if (strcmp(scenario, "denied") == 0) return LIBUSB_ERROR_ACCESS;
    handles[dev->index].device = dev;
    *h = &handles[dev->index];
    return 0;
}
void libusb_close(libusb_device_handle *h) { (void)h; }
int libusb_get_string_descriptor_ascii(libusb_device_handle *h, uint8_t idx, unsigned char *data, int len)
{
    (void)idx;
    const char *s = h->device->index ? "SECOND" : "FIRST";
    if (strcmp(scenario, "serial-error") == 0) return LIBUSB_ERROR_IO;
    snprintf((char *)data, (size_t)len, "%s", s);
    return (int)strlen(s);
}
int libusb_get_configuration(libusb_device_handle *h, int *config)
{
    (void)h;
    if (strcmp(scenario, "config-error") == 0) return LIBUSB_ERROR_IO;
    *config = strstr(scenario, "configured") || strstr(scenario, "normal") ? 1 : 0;
    return 0;
}
int libusb_get_config_descriptor_by_value(libusb_device *dev, uint8_t value, struct libusb_config_descriptor **out)
{
    (void)dev; (void)value;
    static struct libusb_config_descriptor d;
    if (strcmp(scenario, "no-config-one") == 0) return LIBUSB_ERROR_NOT_FOUND;
    *out = &d;
    return 0;
}
void libusb_free_config_descriptor(struct libusb_config_descriptor *d) { (void)d; }
int libusb_set_configuration(libusb_device_handle *h, int value)
{
    printf("STATE_CHANGE serial=%s value=%d\n", h->device->index ? "SECOND" : "FIRST", value);
    return strcmp(scenario, "set-error") == 0 ? LIBUSB_ERROR_IO : 0;
}
const char *libusb_error_name(int error) { (void)error; return "mock USB failure"; }
