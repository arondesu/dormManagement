document.addEventListener('DOMContentLoaded', () => {
    const statusSelect = document.getElementById('statusSelect');
    const buildingSelect = document.getElementById('buildingSelect');
    const roomSelect = document.getElementById('roomSelect');
    const monthlyRate = document.getElementById('monthlyRate');
    const endDate = document.getElementById('endDate');
    const buildingHidden = document.getElementById('buildingHidden');
    const roomHidden = document.getElementById('roomHidden');

    if (!statusSelect || !buildingSelect || !roomSelect || !monthlyRate || !endDate || !buildingHidden || !roomHidden) {
        return;
    }

    function syncHidden() {
        buildingHidden.value = buildingSelect.value;
        roomHidden.value = roomSelect.value;
    }

    function updateReadOnlyState() {
        const completed = statusSelect.value === 'completed';
        buildingSelect.disabled = completed;
        roomSelect.disabled = completed;
        monthlyRate.readOnly = completed;
        endDate.readOnly = completed;
        syncHidden();
    }

    function loadRoomsForBuilding(buildingId) {
        if (!buildingId) {
            roomSelect.innerHTML = '<option value="">Select a room</option>';
            syncHidden();
            return;
        }

        fetch(`/get_rooms/${buildingId}`)
            .then((res) => res.json())
            .then((data) => {
                const rooms = data.rooms || data;
                const currentRoomNumber = roomHidden.value;

                roomSelect.innerHTML = '';
                if (rooms.length) {
                    rooms.forEach((rn) => {
                        const opt = document.createElement('option');
                        opt.value = rn;
                        opt.textContent = rn;
                        if (rn === currentRoomNumber) {
                            opt.selected = true;
                        }
                        roomSelect.appendChild(opt);
                    });
                } else {
                    const opt = document.createElement('option');
                    opt.value = '';
                    opt.textContent = 'No rooms available';
                    roomSelect.appendChild(opt);
                }
                syncHidden();
            })
            .catch(() => {
                // no-op
            });
    }

    buildingSelect.addEventListener('change', function onBuildingChange() {
        loadRoomsForBuilding(this.value);
        syncHidden();
    });

    roomSelect.addEventListener('change', syncHidden);
    statusSelect.addEventListener('change', updateReadOnlyState);

    syncHidden();
    updateReadOnlyState();
});
