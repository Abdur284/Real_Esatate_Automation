import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const auth = vi.hoisted(() => ({ requestResetCode: vi.fn(), verifyResetCode: vi.fn(), resetPassword: vi.fn() }));
vi.mock('../api', () => ({ default: { auth } }));
vi.mock('../auth/AuthContext', () => ({
    useAuth: () => ({ user: null, profile: null, ready: true, login: vi.fn(), signup: vi.fn() }),
    authErrorMessage: (e) => e.message,
}));

const { default: Signup } = await import('./Signup');

const type = (label, value) => fireEvent.change(screen.getByLabelText(label), { target: { value } });

describe('forgot password', () => {
    beforeEach(() => {
        Object.values(auth).forEach((f) => f.mockReset());
        render(<MemoryRouter initialEntries={['/signup?tab=login']}><Signup /></MemoryRouter>);
        fireEvent.click(screen.getByRole('button', { name: 'Forgot password?' }));
    });

    it('sends a code, checks it, and sets the new password', async () => {
        auth.requestResetCode.mockResolvedValue({ message: 'If an account exists for this email, a verification code has been sent to it.' });
        auth.verifyResetCode.mockResolvedValue({ reset_token: 'tok-123456789' });
        auth.resetPassword.mockResolvedValue({ message: 'ok' });

        type('Email Address', 'buyer@test.com');
        fireEvent.click(screen.getByRole('button', { name: /Send Verification Code/ }));
        expect(await screen.findByText('Enter verification code')).toBeTruthy();
        expect(auth.requestResetCode).toHaveBeenCalledWith('buyer@test.com');
        expect(screen.getByText(/resend in 60s/)).toBeTruthy();

        type('Verification Code', '12a3456');   // non-digits are dropped
        fireEvent.click(screen.getByRole('button', { name: /Verify Code/ }));
        expect(await screen.findByText('Set a new password')).toBeTruthy();
        expect(auth.verifyResetCode).toHaveBeenCalledWith('buyer@test.com', '123456');

        type('New Password', 'newpass123');
        type('Confirm New Password', 'newpass123');
        fireEvent.click(screen.getByRole('button', { name: /Reset Password/ }));
        expect(await screen.findByText(/Your password has been changed/)).toBeTruthy();
        expect(auth.resetPassword).toHaveBeenCalledWith('tok-123456789', 'newpass123');
        expect(screen.getByText('Welcome back')).toBeTruthy();
    });

    it('shows the server error for a wrong code and stays on the code step', async () => {
        auth.requestResetCode.mockResolvedValue({ message: 'sent' });
        auth.verifyResetCode.mockRejectedValue(new Error('That code is not correct.'));

        type('Email Address', 'buyer@test.com');
        fireEvent.click(screen.getByRole('button', { name: /Send Verification Code/ }));
        await screen.findByText('Enter verification code');
        type('Verification Code', '000000');
        fireEvent.click(screen.getByRole('button', { name: /Verify Code/ }));
        expect(await screen.findByText('That code is not correct.')).toBeTruthy();
        expect(screen.getByText('Enter verification code')).toBeTruthy();
    });

    it('requires matching passwords', async () => {
        auth.requestResetCode.mockResolvedValue({ message: 'sent' });
        auth.verifyResetCode.mockResolvedValue({ reset_token: 'tok-123456789' });
        type('Email Address', 'buyer@test.com');
        fireEvent.click(screen.getByRole('button', { name: /Send Verification Code/ }));
        await screen.findByText('Enter verification code');
        type('Verification Code', '123456');
        fireEvent.click(screen.getByRole('button', { name: /Verify Code/ }));
        await screen.findByText('Set a new password');
        type('New Password', 'newpass123');
        type('Confirm New Password', 'different1');
        fireEvent.click(screen.getByRole('button', { name: /Reset Password/ }));
        expect(screen.getByText('Passwords do not match.')).toBeTruthy();
        expect(auth.resetPassword).not.toHaveBeenCalled();
    });
});
