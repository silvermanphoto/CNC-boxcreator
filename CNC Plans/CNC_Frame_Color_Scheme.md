# CNC Frame Color Scheme for Fusion 360

Use these colors for all CNC frame visualization in Fusion 360.

## Color Assignments

| Operation | Hex Color | RGB | Description |
|-----------|-----------|-----|-------------|
| **Perimeter Cuts** | `#49bcf6` | (73, 188, 246) | Light blue - outer cut paths |
| **Interior Fill** | `#49bcf6` | (73, 188, 246) | Light blue - non-rabbeted interior areas |
| **Rabbets** | `#e498c3` | (228, 152, 195) | Pink - rabbet pocket cuts |
| **Holes** | `#f10031` | (241, 0, 49) | Red - drill holes |
| **Window Cutout** | `#e8cf6c` | (232, 207, 108) | Yellow/Gold - window or interior cutouts |

## Visual Summary

```
┌─────────────────────────────┐
│  PINK (#e498c3) - Rabbets   │
│  ┌───────────────────────┐  │
│  │                       │  │
│  │  LIGHT BLUE (#49bcf6) │  │
│  │  Interior Fill        │  │
│  │     ┌───────────┐     │  │
│  │     │  YELLOW   │     │  │
│  │     │ (#e8cf6c) │     │  │
│  │     │  Window   │     │  │
│  │     └───────────┘     │  │
│  │                       │  │
│  └───────────────────────┘  │
└─────────────────────────────┘

RED (#f10031) - Holes (circles for mounting/ventilation)
```

## Fusion 360 Appearance Names

When creating these in Fusion, use these appearance names:
- `VIZ_Perimeter` - Light blue (#49bcf6)
- `VIZ_Rabbets` - Pink (#e498c3)
- `VIZ_Holes` - Red (#f10031)
- `VIZ_Window` - Yellow (#e8cf6c)

## Z-Level Stacking (for visibility)

To prevent Z-fighting when bodies overlap:
- Perimeter: Z = 0.00 cm
- Interior Fill: Z = 0.015 cm
- Rabbets: Z = 0.02 cm
- Holes/Window: Z = 0.04 cm

---
*Created: January 2026*
*For use with Joel Silverman's CNC box/frame projects*
