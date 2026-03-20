import 'package:flutter/material.dart';
import 'app_logo_badge.dart';
import '../services/api_service.dart';

class AppNavBar extends StatefulWidget {
  final String? currentUserName;
  final String? currentUserRole;
  final String? currentUserSpecialty;
  final VoidCallback? onSettingsTap;
  final VoidCallback? onLogout;
  final List<NavBarItem> navItems;
  final String? activeItem;

  const AppNavBar({
    Key? key,
    this.currentUserName,
    this.currentUserRole,
    this.currentUserSpecialty,
    this.onSettingsTap,
    this.onLogout,
    this.navItems = const [],
    this.activeItem,
  }) : super(key: key);

  @override
  State<AppNavBar> createState() => _AppNavBarState();
}

class _AppNavBarState extends State<AppNavBar> {
  String? _storedName;
  String? _storedRole;

  @override
  void initState() {
    super.initState();
    _loadStoredUser();
  }

  Future<void> _loadStoredUser() async {
    final info = await ApiService.getUserInfo();
    if (!mounted || info == null) return;
    setState(() {
      _storedName = info['full_name'] as String?;
      _storedRole = info['role'] as String?;
    });
  }

  String get _effectiveName {
    final passed = widget.currentUserName?.trim() ?? '';
    if (passed.isNotEmpty) return passed;
    return _storedName?.trim() ?? '';
  }

  String get _effectiveRole {
    final passed = widget.currentUserRole?.trim() ?? '';
    if (passed.isNotEmpty) return passed;
    return _storedRole?.trim() ?? '';
  }

  String _getInitials(String name) {
    if (name.trim().isEmpty) return '?';
    final parts = name.trim().split(RegExp(r'\s+'));
    if (parts.length == 1) {
      // Single word — use first two letters so always 2 chars
      final word = parts[0];
      return word.length >= 2
          ? word.substring(0, 2).toUpperCase()
          : word[0].toUpperCase();
    }
    return '${parts.first[0]}${parts.last[0]}'.toUpperCase();
  }

  String _getRoleLabel(String? role, String? specialty) {
    if (role == 'doctor') {
      if (specialty != null && specialty.trim().isNotEmpty)
        return specialty.trim();
      return 'Doctor';
    }
    if (role == 'hospital_admin') return 'Hospital Admin';
    if (role == 'platform_admin') return 'Platform Admin';
    return role ?? '';
  }

  @override
  Widget build(BuildContext context) {
    final displayName = _effectiveName;
    final displayRole = _effectiveRole;
    return Padding(
      padding: const EdgeInsets.only(top: 10),
      child: Center(
        child: FractionallySizedBox(
          widthFactor: 0.95,
          child: Container(
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(40),
              border: Border.all(
                color: const Color.fromARGB(255, 129, 129, 129),
                width: 0.8,
              ),
            ),
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 5),
            child: Row(
              children: [
                const AppLogoBadge(size: 60),

                // Spacer pushes everything else to the right
                const Spacer(),

                // Navigation items — spread with generous gaps between them
                ...widget.navItems.map((item) {
                  final isActive = widget.activeItem == item.label;
                  return Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 20),
                    child: MouseRegion(
                      cursor: SystemMouseCursors.click,
                      child: GestureDetector(
                        onTap: item.onTap,
                        child: Text(
                          item.label,
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight:
                                isActive ? FontWeight.w600 : FontWeight.w500,
                            color:
                                isActive
                                    ? const Color.fromARGB(255, 59, 71, 5)
                                    : Colors.grey[700],
                          ),
                        ),
                      ),
                    ),
                  );
                }),

                const SizedBox(width: 20),

                // User info container
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 18,
                    vertical: 9,
                  ),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    // borderRadius: BorderRadius.circular(30),
                    // border: Border.all(
                    //   color: const Color.fromARGB(255, 155, 155, 155),
                    //   width: 0.8,
                    // ),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      CircleAvatar(
                        radius: 16,
                        backgroundColor: const Color(0xFF8B9E3A),
                        child: Text(
                          _getInitials(displayName),
                          style: const TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.bold,
                            fontSize: 13,
                          ),
                        ),
                      ),
                      const SizedBox(width: 10),
                      if (displayName.isNotEmpty)
                        Column(
                          mainAxisSize: MainAxisSize.min,
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              displayName,
                              style: const TextStyle(
                                fontSize: 14,
                                fontWeight: FontWeight.w600,
                                color: Colors.black,
                              ),
                            ),
                            Text(
                              _getRoleLabel(
                                displayRole.isNotEmpty ? displayRole : null,
                                widget.currentUserSpecialty,
                              ),
                              style: TextStyle(
                                fontSize: 13,
                                color: Colors.grey[600],
                              ),
                            ),
                          ],
                        ),
                    ],
                  ),
                ),

                const SizedBox(width: 20),

                // Dropdown menu for Profile and Logout
                PopupMenuButton<String>(
                  onSelected: (value) {
                    if (value == 'Logout') {
                      widget.onLogout?.call();
                    }
                  },
                  offset: const Offset(0, 40),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                  color: Colors.white,
                  itemBuilder: (BuildContext context) {
                    return [
                      PopupMenuItem<String>(
                        value: 'Profile',
                        child: Row(
                          children: [
                            Icon(
                              Icons.person_outline,
                              color: Colors.black,
                              size: 20,
                            ),
                            const SizedBox(width: 10),
                            const Text(
                              'Profile',
                              style: TextStyle(fontSize: 14),
                            ),
                          ],
                        ),
                      ),
                      PopupMenuItem<String>(
                        value: 'Logout',
                        child: Row(
                          children: [
                            Icon(
                              Icons.logout_outlined,
                              color: Colors.redAccent,
                              size: 20,
                            ),
                            const SizedBox(width: 10),
                            const Text(
                              'Logout',
                              style: TextStyle(
                                fontSize: 14,
                                color: Colors.redAccent,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ];
                  },
                  icon: Icon(
                    Icons.arrow_drop_down_outlined,
                    color: Colors.black,
                    size: 24,
                  ), // Outlined dropdown icon
                ),

                const SizedBox(width: 20),

                // Settings icon
                MouseRegion(
                  cursor: SystemMouseCursors.click,
                  child: GestureDetector(
                    onTap: widget.onSettingsTap,
                    child: Icon(
                      Icons.settings_outlined,
                      color: Colors.grey[600],
                      size: 22,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class NavBarItem {
  final String label;
  final VoidCallback onTap;

  NavBarItem({required this.label, required this.onTap});
}
