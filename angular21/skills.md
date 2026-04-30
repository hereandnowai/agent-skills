---
name: angular21
description: Build Angular 21 frontend applications using modern Angular patterns. Use this skill whenever the user asks to create, scaffold, or write Angular components, services, directives, pipes, routes, forms, or any Angular code — especially when they mention Angular 21, signal forms, zoneless, Angular ARIA, Vitest, MCP server, or building a frontend with Angular. Trigger on phrases like "Angular app", "Angular component", "Angular service", "build with Angular", "Angular frontend", "Angular 21", "signals in Angular", "signal forms", or any request to generate or refactor Angular TypeScript/HTML/SCSS code.
---

# Angular 21 Frontend Skill

Angular 21 was released November 20, 2025. It completes Angular's shift to a modern, signals-first, zoneless-by-default architecture. Always write idiomatic Angular 21 code using the defaults below.

## Angular 21 Defaults (new projects)

| Feature | Angular 21 Default |
|---|---|
| Change detection | **Zoneless** (no Zone.js) |
| Components | **Standalone** (no NgModule) |
| Test runner | **Vitest** (not Karma) |
| HttpClient | **Auto-provided** (no manual setup needed) |
| Forms | **Signal Forms** (experimental) or Reactive Forms |
| Zone.js | **Not included** by default |

---

## Core Principles for Angular 21

1. **Standalone everything** — No NgModule unless maintaining a legacy project.
2. **Zoneless by default** — New apps use `provideZonelessChangeDetection()`. Rely entirely on signals for reactivity.
3. **Signals-first** — `signal()`, `computed()`, `effect()`, `linkedSignal()`, `toSignal()` — all stable. Prefer over RxJS for local/shared state.
4. **Signal Forms** for new forms — experimental but the intended path forward. Fall back to Reactive Forms for production-critical apps.
5. **`inject()` only** — Never use constructor DI.
6. **New control flow** — `@if`, `@for`, `@switch` always. Never `*ngIf`, `*ngFor`.
7. **Vitest** — Default test runner; no `fakeAsync`/`tick` (tests are zoneless, use async mocks).

---

## Project Setup

```bash
npm create @angular/cli@21 my-app
# or
ng new my-app --style=scss --routing --ssr=false
```

### Key dependencies (Angular 21)
```json
{
  "dependencies": {
    "@angular/core": "^21.0.0",
    "@angular/common": "^21.0.0",
    "@angular/router": "^21.0.0",
    "@angular/forms": "^21.0.0",
    "@angular/platform-browser": "^21.0.0"
  }
}
```

### app.config.ts (Angular 21 defaults)
```typescript
import { ApplicationConfig } from '@angular/core';
import { provideRouter, withViewTransitions } from '@angular/router';
import { provideZonelessChangeDetection } from '@angular/core';
import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideZonelessChangeDetection(),  // Default in v21
    provideRouter(routes, withViewTransitions()),
    // HttpClient is auto-provided — no provideHttpClient() needed
  ]
};
```

---

## Component Anatomy

```typescript
import { Component, signal, computed, inject } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-user-card',
  standalone: true,
  imports: [RouterLink],
  template: `
    <div class="card">
      @if (user(); as u) {
        <h2>{{ u.name }}</h2>
        <p>{{ u.email }}</p>
        <a [routerLink]="['/users', u.id]">View Profile</a>
      } @else {
        <p>No user loaded.</p>
      }

      @for (tag of tags(); track tag.id) {
        <span class="tag">{{ tag.label }}</span>
      } @empty {
        <span>No tags</span>
      }

      @switch (status()) {
        @case ('active')   { <span class="green">Active</span> }
        @case ('inactive') { <span class="red">Inactive</span> }
        @default           { <span>Unknown</span> }
      }
    </div>
  `,
  styleUrl: './user-card.component.scss'
})
export class UserCardComponent {
  private userService = inject(UserService);

  user = this.userService.currentUser;
  tags = signal([{ id: 1, label: 'admin' }]);
  status = computed(() => this.user()?.status ?? 'unknown');
}
```

---

## Signal Forms (Experimental — Angular 21)

Signal Forms replace the RxJS-based reactive forms pattern. Recommended for new code when experimental is acceptable.

```typescript
import { Component } from '@angular/core';
import { FormField, FormGroup, SignalFormsModule } from '@angular/forms/experimental';

@Component({
  standalone: true,
  imports: [SignalFormsModule],
  template: `
    <form (submit)="submit()">
      <input [formField]="form.fields.email" type="email" />
      @if (form.fields.email.errors(); as errors) {
        @if (errors['required']) { <span>Email is required</span> }
        @if (errors['email'])    { <span>Invalid email</span> }
      }

      <input [formField]="form.fields.password" type="password" />
      <button type="submit" [disabled]="!form.valid()">Submit</button>
    </form>
  `
})
export class LoginComponent {
  form = new FormGroup({
    email: new FormField('', { validators: [required, email] }),
    password: new FormField('', { validators: [minLength(8)] })
  });

  submit() {
    if (this.form.valid()) {
      console.log(this.form.value());  // fully typed signal value
    }
  }
}
```

> **Note**: Signal Forms are experimental in v21. For production stability, use standard Reactive Forms (still fully supported). See `references/signal-forms.md` for full API.

### Reactive Forms (stable, still valid)
```typescript
import { ReactiveFormsModule, FormGroup, FormControl, Validators } from '@angular/forms';

@Component({
  standalone: true,
  imports: [ReactiveFormsModule],
  template: `
    <form [formGroup]="form" (ngSubmit)="submit()">
      <input formControlName="email" type="email" />
      @if (form.get('email')?.invalid && form.get('email')?.touched) {
        <span>Email is required</span>
      }
      <button type="submit" [disabled]="form.invalid">Submit</button>
    </form>
  `
})
export class LoginComponent {
  form = new FormGroup({
    email: new FormControl('', [Validators.required, Validators.email]),
    password: new FormControl('', Validators.minLength(8))
  });
  submit() { if (this.form.valid) console.log(this.form.value); }
}
```

---

## Services with Signals

```typescript
import { Injectable, signal, computed, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { toSignal } from '@angular/core/rxjs-interop';

@Injectable({ providedIn: 'root' })
export class UserService {
  private http = inject(HttpClient);  // auto-provided in v21

  private _users = signal<User[]>([]);
  users = this._users.asReadonly();
  userCount = computed(() => this._users().length);

  topUsers = toSignal(this.http.get<User[]>('/api/users/top'), { initialValue: [] });

  addUser(user: User) {
    this._users.update(list => [...list, user]);
  }
}
```

---

## Routing

```typescript
// app.routes.ts
import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', redirectTo: 'home', pathMatch: 'full' },
  {
    path: 'home',
    loadComponent: () => import('./home/home.component').then(m => m.HomeComponent)
  },
  {
    path: 'dashboard',
    loadChildren: () => import('./dashboard/dashboard.routes').then(m => m.DASHBOARD_ROUTES),
    canActivate: [authGuard]
  }
];
```

---

## Dependency Injection — `inject()` only

```typescript
// ✅ Angular 21
export class MyComponent {
  private userService = inject(UserService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
}

// ❌ Never — constructor DI is outdated
export class MyComponent {
  constructor(private userService: UserService) {}
}
```

---

## Angular ARIA (Developer Preview)

Headless accessibility primitives — no styles, full ARIA roles, keyboard nav, and focus management. Build your own styled components on top.

```bash
ng add @angular/aria
```

```typescript
import { AriaAccordion, AriaAccordionItem } from '@angular/aria';

@Component({
  standalone: true,
  imports: [AriaAccordion, AriaAccordionItem],
  template: `
    <aria-accordion>
      <aria-accordion-item>
        <button ariaAccordionTrigger>Section 1</button>
        <div ariaAccordionPanel>Content here</div>
      </aria-accordion-item>
    </aria-accordion>
  `
})
export class FaqComponent {}
```

Available primitives in v21: **Accordion, Combobox, Tabs, Menu, Listbox, Dialog**.  
See `references/angular-aria.md` for full usage.

---

## Testing with Vitest (Default in v21)

Vitest replaces Karma/Jasmine as the default. Tests run zoneless — no `fakeAsync`/`tick`.

```typescript
import { TestBed } from '@angular/core/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { UserService } from './user.service';

describe('UserService', () => {
  let service: UserService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(),
        provideHttpClient(),
        provideHttpClientTesting()
      ]
    });
    service = TestBed.inject(UserService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  it('should have empty users initially', () => {
    expect(service.users()).toEqual([]);
  });

  // Use async/await instead of fakeAsync/tick
  it('should fetch top users', async () => {
    const req = httpMock.expectOne('/api/users/top');
    req.flush([{ id: 1, name: 'Alice' }]);
    await Promise.resolve();
    expect(service.topUsers().length).toBe(1);
  });
});
```

---

## Angular MCP Server

Angular 21 ships a built-in MCP server for AI-assisted development:

```bash
ng mcp                        # Start MCP server
ng mcp --experimental-tools   # Include experimental tools (-E shorthand)
```

Tools available: `search_documentation`, `get_best_practices`, `find_examples`, `list_projects`, `onpush_zoneless_migration`, `modernize` (experimental), `ai_tutor` (experimental).

---

## SSR / Hydration

```typescript
// app.config.server.ts
import { provideServerRendering } from '@angular/platform-server';
import { provideClientHydration, withIncrementalHydration } from '@angular/platform-browser';
import { provideZonelessChangeDetection } from '@angular/core';

export const serverConfig: ApplicationConfig = {
  providers: [
    provideZonelessChangeDetection(),
    provideServerRendering(),
    provideClientHydration(withIncrementalHydration())
  ]
};
```

---

## Angular Material (if requested)

```bash
ng add @angular/material
```

```typescript
import { MatButtonModule } from '@angular/material/button';
@Component({ standalone: true, imports: [MatButtonModule] })
```

---

## File & Folder Conventions

```
src/
  app/
    core/
      services/       # Singleton services (providedIn: 'root')
      guards/
      interceptors/
    shared/
      components/     # Reusable UI
      pipes/
      directives/
    features/
      home/
        home.component.ts
        home.component.html
        home.component.scss
      dashboard/
        dashboard.routes.ts
    app.routes.ts
    app.config.ts
    app.component.ts
```

---

## Checklist Before Outputting Angular 21 Code

- [ ] All components are `standalone: true`
- [ ] Using `@if` / `@for` / `@switch` (not `*ngIf` etc.)
- [ ] Using `inject()` for DI (not constructor)
- [ ] `provideZonelessChangeDetection()` in app.config.ts
- [ ] No manual `provideHttpClient()` (auto-provided in v21)
- [ ] Signals used for all reactive state
- [ ] `track` expression used in every `@for`
- [ ] Tests use Vitest patterns — async/await, no `fakeAsync`/`tick`
- [ ] No Zone.js imports anywhere

---

## Reference Files

- `references/signals-patterns.md` — Advanced signal patterns (`resource()`, `httpResource()`, signal store)
- `references/signal-forms.md` — Full Signal Forms API (experimental)
- `references/angular-aria.md` — Angular ARIA primitives guide
- `references/migration.md` — Migrating from Angular 20 and older versions