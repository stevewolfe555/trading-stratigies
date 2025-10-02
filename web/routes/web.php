<?php

use Illuminate\Support\Facades\Route;

// Redirect root to watchlist
Route::redirect('/', '/watchlist');

// Watchlist - Multi-stock overview
Route::view('watchlist', 'watchlist')
    ->name('watchlist');

// Stock Detail - Single stock analysis
Route::view('stock/{symbol?}', 'stock-detail')
    ->name('stock.detail');

// Strategies - Strategy management
Route::view('strategies', 'strategies')
    ->name('strategies');

// Account - Portfolio & trades
Route::view('account', 'account')
    ->name('account');

// Backtesting - Run and view backtests
Route::view('backtesting', 'backtesting')
    ->name('backtesting');

Route::view('profile', 'profile')
    ->middleware(['auth'])
    ->name('profile');

require __DIR__.'/auth.php';
