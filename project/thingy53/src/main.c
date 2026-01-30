#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/uuid.h>
#include <zephyr/bluetooth/gatt.h>
#include <zephyr/logging/log.h>

LOG_MODULE_REGISTER(main);

// --- UUIDs ---
#define BT_UUID_ESS_VAL 0x181A
#define BT_UUID_TEMP_VAL 0x2A6E
#define BT_UUID_HUMID_VAL 0x2A6F

static int16_t temp_val = 0;
static uint16_t humid_val = 0;

// --- Bluetooth Read Callbacks ---
static ssize_t read_temp(struct bt_conn *conn, const struct bt_gatt_attr *attr,
                         void *buf, uint16_t len, uint16_t offset) {
    return bt_gatt_attr_read(conn, attr, buf, len, offset, &temp_val, sizeof(temp_val));
}

static ssize_t read_humid(struct bt_conn *conn, const struct bt_gatt_attr *attr,
                          void *buf, uint16_t len, uint16_t offset) {
    return bt_gatt_attr_read(conn, attr, buf, len, offset, &humid_val, sizeof(humid_val));
}

// --- Service Definition ---
BT_GATT_SERVICE_DEFINE(ess_svc,
    BT_GATT_PRIMARY_SERVICE(BT_UUID_DECLARE_16(BT_UUID_ESS_VAL)),
    BT_GATT_CHARACTERISTIC(BT_UUID_DECLARE_16(BT_UUID_TEMP_VAL),
                           BT_GATT_CHRC_READ | BT_GATT_CHRC_NOTIFY,
                           BT_GATT_PERM_READ, read_temp, NULL, &temp_val),
    BT_GATT_CCC(NULL, BT_GATT_PERM_READ | BT_GATT_PERM_WRITE),
    BT_GATT_CHARACTERISTIC(BT_UUID_DECLARE_16(BT_UUID_HUMID_VAL),
                           BT_GATT_CHRC_READ | BT_GATT_CHRC_NOTIFY,
                           BT_GATT_PERM_READ, read_humid, NULL, &humid_val),
    BT_GATT_CCC(NULL, BT_GATT_PERM_READ | BT_GATT_PERM_WRITE),
);

static const struct bt_data ad[] = {
    BT_DATA_BYTES(BT_DATA_FLAGS, (BT_LE_AD_GENERAL | BT_LE_AD_NO_BREDR)),
    BT_DATA(BT_DATA_NAME_COMPLETE, "Thingy_Sensor", 13),
};

int main(void)
{
    int err;
    const struct device *dev_bme680 = DEVICE_DT_GET_ANY(bosch_bme680);

    LOG_INF("Starting Bluetooth...");
    err = bt_enable(NULL);
    if (err) {
        LOG_ERR("Bluetooth init failed (err %d)", err);
        return 0;
    }

    // --- FIX IS HERE ---
    // Changed BT_LE_ADV_CONN_NAME -> BT_LE_ADV_CONN
    // This prevents the "Double Name" error (-22)
    err = bt_le_adv_start(BT_LE_ADV_CONN, ad, ARRAY_SIZE(ad), NULL, 0);
    
    if (err) {
        LOG_ERR("Advertising failed to start (err %d)", err);
        return 0;
    }
    LOG_INF("✅ Advertising as 'Thingy_Sensor'");

    // ... rest of the code (Sensor Check) remains the same ...
    
    // 2. CHECK SENSOR
    bool sensor_ok = true;
    if (!device_is_ready(dev_bme680)) {
        LOG_ERR("❌ BME680 Sensor NOT ready!");
        sensor_ok = false;
    } else {
        LOG_INF("✅ BME680 Sensor Found");
    }

    // 3. MAIN LOOP
    while (1) {
        if (sensor_ok) {
            struct sensor_value temp, humid;
            
            // Try to fetch sample
            if (sensor_sample_fetch(dev_bme680) == 0) {
                sensor_channel_get(dev_bme680, SENSOR_CHAN_AMBIENT_TEMP, &temp);
                sensor_channel_get(dev_bme680, SENSOR_CHAN_HUMIDITY, &humid);

                double t = sensor_value_to_double(&temp);
                double h = sensor_value_to_double(&humid);

                LOG_INF("Read: Temp=%.2f C, Humid=%.2f %%", t, h);

                // Update BLE variables
                temp_val = (int16_t)(t * 100);
                humid_val = (uint16_t)(h * 100);

                // Notify (Send data to Python)
                bt_gatt_notify(NULL, &ess_svc.attrs[1], &temp_val, sizeof(temp_val));
                bt_gatt_notify(NULL, &ess_svc.attrs[4], &humid_val, sizeof(humid_val));
            } else {
                LOG_ERR("Failed to fetch sensor sample");
            }
        } else {
            // Simulate data if sensor is broken so we can still test Python
            temp_val = 2550; // 25.50 C
            bt_gatt_notify(NULL, &ess_svc.attrs[1], &temp_val, sizeof(temp_val));
        }

        k_sleep(K_SECONDS(2));
    }
    return 0;
}