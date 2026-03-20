import 'package:flutter/material.dart';

class AdminSidebar extends StatelessWidget {
  final String activeItem;
  final ValueChanged<String>? onItemSelected;

  const AdminSidebar({Key? key, required this.activeItem, this.onItemSelected})
    : super(key: key);

  static const Color _primaryGreen = Color.fromARGB(255, 59, 71, 5);

  static const List<_AdminMenuItem> _menuItems = [
    _AdminMenuItem(label: 'Users', icon: Icons.people_alt_outlined),
    _AdminMenuItem(label: 'Facilities', icon: Icons.local_hospital_outlined),
    _AdminMenuItem(label: 'Doctors', icon: Icons.medical_services_outlined),
    _AdminMenuItem(label: 'Rooms', icon: Icons.meeting_room_outlined),
  ];

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 250,
      color: _primaryGreen,
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 20, 16, 20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Eleza Admin Panel',
                style: TextStyle(
                  color: Color.fromRGBO(255, 255, 255, 1),
                  fontSize: 20,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 20),
              ..._menuItems.map((item) {
                final isActive = item.label == activeItem;
                return Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: Material(
                    color: isActive ? Colors.white : Colors.transparent,
                    borderRadius: BorderRadius.circular(12),
                    child: InkWell(
                      borderRadius: BorderRadius.circular(12),
                      onTap: () => onItemSelected?.call(item.label),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 12,
                        ),
                        child: Row(
                          children: [
                            Icon(
                              item.icon,
                              color: isActive ? _primaryGreen : Colors.white,
                            ),
                            const SizedBox(width: 12),
                            Text(
                              item.label,
                              style: TextStyle(
                                fontSize: 15,
                                fontWeight:
                                    isActive
                                        ? FontWeight.w700
                                        : FontWeight.w500,
                                color: isActive ? _primaryGreen : Colors.white,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                );
              }),
            ],
          ),
        ),
      ),
    );
  }
}

class _AdminMenuItem {
  final String label;
  final IconData icon;

  const _AdminMenuItem({required this.label, required this.icon});
}
