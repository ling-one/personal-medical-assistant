Component({
  properties: {
    members: { type: Array, value: [] },
    selectedMember: { type: Object, value: null }
  },

  methods: {
    onSelect(e) {
      const member = e.currentTarget.dataset.member
      this.triggerEvent('select', member)
    }
  }
})
