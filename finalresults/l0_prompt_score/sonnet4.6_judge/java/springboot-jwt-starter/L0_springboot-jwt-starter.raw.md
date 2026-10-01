# L0 Prompt Review: springboot-jwt-starter

## Summary

The springboot-jwt-starter prompt is well-specified for the model classes (User, Authority, UserRoleName, UserTokenState) that are the targets of all blackbox tests.

## Completeness (4.5)
Covers User (all getters/setters including setPassword side effect updating lastPasswordResetDate, UserDetails interface methods), Authority (getId/setId/getName/setName/getAuthority), UserRoleName enum (ROLE_USER, ROLE_ADMIN), UserTokenState (two constructors, getters/setters). The setPassword(null) edge case updating lastPasswordResetDate is covered by the general 'also update lastPasswordResetDate' specification.

## Unambiguity (4.5)
Key contracts are precise: setPassword updates lastPasswordResetDate to current timestamp, Authority.getAuthority() returns the enum name string, User.getAuthorities() returns Collection<? extends GrantedAuthority>, Authority implements GrantedAuthority. The default enabled=false is not explicitly stated in the prompt but UserDetails default behavior is standard.

## Testability (4.5)
All blackbox test scenarios (getter/setter pairs, setPassword timestamp side effect, UserDetails interface method returns, Authority.getAuthority string format, UserRoleName enum values, UserTokenState constructor and setters) are directly derivable from the prompt.

## Consistency (4.5)
No conflicts. setPassword(null) updating lastPasswordResetDate is consistent with tests (prompt says setPassword 'must also update'). Authority.getAuthority() returning enum name is consistent with tests. The test verifying default authorities is null is not contradicted by the prompt (no default initialization specified).

## Overall: 4.50
