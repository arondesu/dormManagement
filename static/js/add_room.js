document.addEventListener('DOMContentLoaded', () => {
    const buildingSelect = document.getElementById('building_id');
    const floorSelect = document.getElementById('floor_number');

    if (!buildingSelect || !floorSelect) {
        return;
    }

    buildingSelect.addEventListener('change', function onBuildingChange() {
        const buildingId = this.value;
        floorSelect.innerHTML = '<option value="">Select Floor</option>';

        if (!buildingId) {
            return;
        }

        fetch(`/building_floors/${buildingId}`)
            .then((res) => res.json())
            .then((floors) => {
                floors.forEach((floor) => {
                    const opt = document.createElement('option');
                    opt.value = floor;
                    opt.text = `Floor ${floor}`;
                    floorSelect.appendChild(opt);
                });
            });
    });
});
