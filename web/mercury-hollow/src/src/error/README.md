# Error Handling System

This module provides comprehensive error handling for authentication and authorization errors in the B-Sides application.

## Components

### 1. Error Controller (`error.controller.ts`)
Handles rendering of error pages for different HTTP status codes:
- `/error/401` - Unauthorized errors
- `/error/403` - Forbidden errors  
- `/error/auth-error` - General authentication errors

### 2. Exception Filters (`error.filter.ts`)
- **AuthErrorFilter**: Catches `UnauthorizedException` and `ForbiddenException` and redirects to appropriate error pages
- **GlobalErrorFilter**: Catches all other exceptions and handles them appropriately

### 3. Error Template (`error.hbs`)
A user-friendly error page template that:
- Displays a clear "YOU DONE GOOFED" message
- Shows the specific error code and message
- Provides a "Return to Login" button
- Uses consistent styling with the rest of the application

## How It Works

1. **Authentication Errors**: When a user tries to access a protected route without proper authentication, the `JwtAuthGuard` throws an `UnauthorizedException`
2. **Authorization Errors**: When a user lacks the required permissions, the `RolesGuard` throws a `ForbiddenException`
3. **Exception Filtering**: The `AuthErrorFilter` catches these exceptions and redirects to the appropriate error page
4. **Error Page Rendering**: The `ErrorController` renders the error page with dynamic error information

## Integration

The error handling is automatically integrated into the application through:
- Global exception filters registered in `ErrorModule`
- Error module imported in `AppModule`
- Automatic redirection for 401/403 errors

## Testing

Use the provided test script to verify error handling:
```bash
./scripts/test-error-handling.sh
```

This will test:
- Protected routes without authentication
- Admin routes without proper permissions
- Direct access to error pages

## Customization

To customize error messages or styling:
1. Edit `src/views/error.hbs` for visual changes
2. Modify `src/error/error.controller.ts` for different error data
3. Update `src/error/error.filter.ts` for different redirect behavior
