Component({
  properties: {
    vitalSigns: { type: Object, value: null }
  },

  data: {
    hasSigns: false,
    systolic: 0,
    diastolic: 0,
    heartRate: 0,
    temperature: 0,
    oxygen: 0
  },

  observers: {
    'vitalSigns': function (val) {
      if (val) {
        this.setData({
          hasSigns: true,
          systolic: val.blood_pressure_systolic,
          diastolic: val.blood_pressure_diastolic,
          heartRate: val.heart_rate,
          temperature: val.temperature,
          oxygen: val.oxygen_saturation
        })
      } else {
        this.setData({ hasSigns: false })
      }
    }
  }
})
