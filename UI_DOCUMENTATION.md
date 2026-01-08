# UI Screenshots & Feature Walkthrough

## Admin Interface - "Gérer Panneaux" Tab

This document describes the user interface for the traffic signs explanation management feature.

## Navigation

The admin interface has 5 tabs:
1. **Ajouter Question** - Add new questions
2. **Base de données** - Database management
3. **Gérer Questions** - Manage questions
4. **Gérer Panneaux** - Manage traffic signs ⭐ (NEW)
5. **Ajouter Panneau** - Add new signs

## "Gérer Panneaux" Tab Interface

### Header Section
```
┌────────────────────────────────────────────────────────────────┐
│ 🛠️ Gérer les panneaux                                         │
└────────────────────────────────────────────────────────────────┘
```

### Control Bar
```
┌─────────────────────────────────────────────────────────────────┐
│ 🔍 [Search: Rechercher un panneau ou une explication...     ] │
│                                                                  │
│ [ ] Seulement sans explication    [🔄 Actualiser]              │
└─────────────────────────────────────────────────────────────────┘
```

**Elements:**
- **Search Input**: Full-width search field with magnifying glass icon
- **Toggle Switch**: "Seulement sans explication" - Shows only signs missing explanations
- **Refresh Button**: Reloads the signs list

### Sign Card (Example 1 - WITH Explanation)

```
┌─────────────────────────────────────────────────────────────────┐
│ [IMG]  Virage dangereux à droite                    [Supprimer] │
│ 16x16  Ce panneau signale un virage dangereux                   │
│                                                                   │
│ [Danger] [#A1a] [✅ Explication OK]                             │
│                                                                   │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ Explication                                                  │ │
│ │ ┌─────────────────────────────────────────────────────────┐ │ │
│ │ │ Réduisez votre vitesse et préparez-vous à tourner à     │ │ │
│ │ │ droite. Ce panneau indique un virage prononcé qui peut  │ │ │
│ │ │ être difficile à négocier à vitesse normale.            │ │ │
│ │ └─────────────────────────────────────────────────────────┘ │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│                                   [💾 Enregistrer l'explication] │
└─────────────────────────────────────────────────────────────────┘
```

**Elements:**
- **Image**: 16x16px thumbnail of the traffic sign (if available)
- **Title**: Sign name in bold
- **Description**: Sign description below title
- **Badges**:
  - Category badge (e.g., "Danger", "Interdiction", "Priorité")
  - Number badge (e.g., "#A1a")
  - Status badge:
    - ✅ Green "Explication OK" (has explanation)
    - ❌ Red "Explication manquante" (no explanation)
- **Explanation Textarea**: Multi-line text area for editing
- **Save Button**: Blue button with save icon
- **Delete Button**: Red destructive button in top-right corner

### Sign Card (Example 2 - WITHOUT Explanation)

```
┌─────────────────────────────────────────────────────────────────┐
│        Cédez le passage                              [Supprimer] │
│        Ce panneau indique que vous devez céder...                │
│                                                                   │
│ [Priorité] [#AB4] [❌ Explication manquante]                    │
│                                                                   │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ Explication                                                  │ │
│ │ ┌─────────────────────────────────────────────────────────┐ │ │
│ │ │ Ajoutez une explication claire et concise             │ │ │
│ │ │                                                           │ │ │
│ │ │                                                           │ │ │
│ │ └─────────────────────────────────────────────────────────┘ │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│                                   [💾 Enregistrer l'explication] │
└─────────────────────────────────────────────────────────────────┘
```

**Red badge** clearly indicates this sign needs an explanation.

### Pagination

When there are more than 50 signs:
```
                    [Charger plus]
```

## Color Scheme

### Light Mode
- Background: White (`bg-white`)
- Text: Slate 900 (`text-slate-900`)
- Borders: Slate 200 (`border-slate-200`)
- Cards: Slate 50 (`bg-slate-50`)

### Dark Mode
- Background: Slate 800 (`dark:bg-slate-800`)
- Text: White (`dark:text-white`)
- Borders: Slate 700 (`dark:border-slate-700`)
- Cards: Slate 800 (`dark:bg-slate-800`)

### Badge Colors

**Status Badges:**
- ✅ "Explication OK": Emerald green background, emerald text
  - Light: `bg-emerald-100 text-emerald-700`
  - Dark: `bg-emerald-950/30 text-emerald-300`
  
- ❌ "Explication manquante": Red background, red text
  - Light: `bg-red-100 text-red-700`
  - Dark: `bg-red-950/30 text-red-300`

**Category & Number Badges:**
- Outline style with slate colors
- Light: `border-slate-300 text-slate-900`
- Dark: `border-slate-600 text-slate-white`

## User Interactions

### 1. Search Signs
- Type in the search box to filter signs by:
  - Name
  - Description
  - Explanation content
- Results update in real-time as you type

### 2. Filter Missing Explanations
- Toggle the "Seulement sans explication" switch
- When ON: Shows only signs without explanations
- When OFF: Shows all signs
- Automatically refreshes the list

### 3. Add/Edit Explanation
1. Click in the explanation textarea
2. Type or edit the explanation text
3. Click "Enregistrer l'explication" button
4. Toast notification appears: "Explication enregistrée"
5. Badge automatically updates to "Explication OK"

### 4. Delete Sign
1. Click the red "Supprimer" button
2. Confirmation dialog: "Supprimer ce panneau ?"
3. If confirmed:
   - Sign is deleted from database
   - Toast notification: "Panneau supprimé"
   - Card disappears from list

### 5. Refresh List
- Click the "Actualiser" button
- Reloads all signs from the server
- Useful after adding new signs

### 6. Load More Signs
- Scroll to bottom of list
- Click "Charger plus" button
- Loads next 50 signs

## Responsive Design

The interface is fully responsive:
- **Desktop**: Full-width layout with side-by-side controls
- **Tablet/Mobile**: 
  - Stacked controls (search bar, then toggle/refresh on separate row)
  - Full-width cards
  - Touch-friendly buttons

## Accessibility

- All form fields have labels
- Color contrast meets WCAG standards
- Icons have descriptive text
- Keyboard navigation supported
- Screen reader friendly

## Toast Notifications

Success notifications appear in the bottom-right corner:
- ✅ "Explication enregistrée" (green)
- ✅ "Panneau supprimé" (green)

Error notifications:
- ❌ "Erreur lors de l'enregistrement" (red)
- ❌ "Erreur lors de la suppression" (red)
- ❌ "Erreur lors du chargement des panneaux" (red)

## Loading States

While loading:
- Three skeleton cards appear (animated placeholders)
- Loading spinner during background operations
- Buttons disabled during save/delete operations

## Example Workflow

### Adding an Explanation

1. **Initial State**: Open "Gérer Panneaux" tab
   - See list of signs, some with red "Explication manquante" badges

2. **Filter**: Toggle "Seulement sans explication"
   - List updates to show only signs needing explanations

3. **Find Sign**: Use search to find specific sign
   - Type "Cédez" in search box
   - "Cédez le passage" sign appears

4. **Add Explanation**: 
   - Click in explanation textarea
   - Type: "Ce panneau triangulaire pointe vers le bas indique que vous devez céder le passage aux véhicules circulant sur la route que vous vous apprêtez à rejoindre. Ralentissez et préparez-vous à vous arrêter si nécessaire."

5. **Save**:
   - Click "Enregistrer l'explication"
   - Toast: "Explication enregistrée" ✅
   - Badge changes from ❌ red to ✅ green

6. **Verify**:
   - Sign no longer appears in "missing" filter
   - Explanation is saved and visible

## Technical Details

### State Management
```javascript
const [manageSigns, setManageSigns] = useState([]);
const [manageSignsSearch, setManageSignsSearch] = useState('');
const [manageSignsLoading, setManageSignsLoading] = useState(false);
const [manageSignsOnlyMissing, setManageSignsOnlyMissing] = useState(true);
```

### API Calls
```javascript
// Fetch signs
GET /api/admin/signs?missingOnly={bool}&limit={int}&offset={int}

// Update explanation
PATCH /api/admin/signs/{id}/explanation
Body: { "explanation": "text" }

// Delete sign
DELETE /api/admin/signs/{id}
```

### Data Structure
```javascript
{
  id: "uuid",
  number: "A1a",
  name: "Virage dangereux à droite",
  description: "Ce panneau signale...",
  image_url: "https://...",
  category: "Danger",
  explanation: "Réduisez votre vitesse...",
  has_explanation: true,
  created_at: "2026-01-08T09:48:18.697259"
}
```

## Comparison with "Gérer Questions" Tab

The "Gérer Panneaux" interface mirrors the "Gérer Questions" interface for consistency:

| Feature | Questions | Panneaux (Signs) |
|---------|-----------|------------------|
| Search | ✅ | ✅ |
| Missing-only filter | ✅ | ✅ |
| Refresh button | ✅ | ✅ |
| Explanation textarea | ✅ | ✅ |
| Save button | ✅ | ✅ |
| Delete button | ✅ | ✅ |
| Status badges | ✅ | ✅ |
| Load more | ✅ | ✅ |
| Card layout | ✅ | ✅ (with image) |

The main difference is that sign cards include:
- Thumbnail image
- Number badge (e.g., "#A1a")
- Visual representation of the sign

This makes it easy for administrators who are already familiar with the question management interface to use the sign management interface.
